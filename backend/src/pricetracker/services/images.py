"""Image storage: validated uploads and SSRF-safe URL imports.

Every accepted image is decoded with Pillow, size-limited, stripped of metadata
and re-encoded to WebP, so what is stored is always a clean raster image. SVG and
other active formats are rejected. URL imports only fetch public https hosts: DNS
is resolved once, every address must be globally routable, the connection is
pinned to the validated address (SNI keeps TLS verification on the hostname), and
each redirect is re-validated.
"""

from __future__ import annotations

import hashlib
import ipaddress
import socket
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from sqlalchemy.orm import Session

from pricetracker.models import Image
from pricetracker.models.enums import ImageSource
from pricetracker.services.errors import NotFound, ValidationFailed
from pricetracker.settings import get_settings

PILImage.MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
MAX_REDIRECTS = 3


class UnsafeUrl(ValidationFailed):
    code = "unsafe_url"


def _process_image(data: bytes) -> tuple[bytes, int, int]:
    settings = get_settings()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ValidationFailed(
            f"A imagem excede {settings.max_upload_mb} MB.", code="image_too_large"
        )
    try:
        with PILImage.open(BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ALLOWED_FORMATS:
            raise ValidationFailed(
                "Formato não suportado. Use JPEG, PNG ou WebP.", code="image_format"
            )
        with PILImage.open(BytesIO(data)) as source:
            source.seek(0)
            converted = (
                source.convert("RGBA")
                if source.mode in ("RGBA", "LA", "P")
                else source.convert("RGB")
            )
            converted.thumbnail((settings.image_max_dimension, settings.image_max_dimension))
            out = BytesIO()
            converted.save(out, format="WEBP", quality=85, method=5)
            return out.getvalue(), converted.width, converted.height
    except ValidationFailed:
        raise
    except (UnidentifiedImageError, OSError, PILImage.DecompressionBombError, SyntaxError) as exc:
        raise ValidationFailed(
            "Arquivo de imagem inválido ou corrompido.", code="image_invalid"
        ) from exc


def store_image(
    db: Session,
    *,
    data: bytes,
    owner_user_id: uuid.UUID | None,
    source: ImageSource,
    source_url: str | None = None,
    attribution: str | None = None,
    license: str | None = None,
    alt_text: str | None = None,
) -> Image:
    processed, width, height = _process_image(data)
    return _save(
        db,
        processed,
        "image/webp",
        ".webp",
        owner_user_id=owner_user_id,
        source=source,
        width=width,
        height=height,
        source_url=source_url,
        attribution=attribution,
        license=license,
        alt_text=alt_text,
    )


def store_trusted_svg(
    db: Session, *, data: bytes, storage_name: str, alt_text: str, license: str
) -> Image:
    """Store a project-shipped SVG illustration (never user input)."""
    return _save(
        db,
        data,
        "image/svg+xml",
        ".svg",
        owner_user_id=None,
        source=ImageSource.SEED,
        width=None,
        height=None,
        license=license,
        alt_text=alt_text,
        storage_name=storage_name,
    )


def _save(
    db: Session,
    payload: bytes,
    content_type: str,
    suffix: str,
    *,
    owner_user_id: uuid.UUID | None,
    source: ImageSource,
    width: int | None,
    height: int | None,
    source_url: str | None = None,
    attribution: str | None = None,
    license: str | None = None,
    alt_text: str | None = None,
    storage_name: str | None = None,
) -> Image:
    settings = get_settings()
    image_id = uuid.uuid4()
    folder = "global" if owner_user_id is None else str(owner_user_id)
    name = storage_name or f"{image_id}{suffix}"
    key = f"{folder}/{name}"
    path = settings.uploads_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)
    image = Image(
        id=image_id,
        owner_user_id=owner_user_id,
        storage_key=key,
        content_type=content_type,
        width=width,
        height=height,
        byte_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        source=source.value,
        source_url=source_url,
        attribution=attribution,
        license=license,
        alt_text=alt_text,
    )
    db.add(image)
    db.flush()
    return image


def image_path(image: Image) -> Path:
    root = get_settings().uploads_dir.resolve()
    path = (root / image.storage_key).resolve()
    if not path.is_relative_to(root):
        raise NotFound("Imagem não encontrada.")
    return path


def get_visible_image(db: Session, image_id: uuid.UUID, user_id: uuid.UUID) -> Image:
    image = db.get(Image, image_id)
    if image is None or (image.owner_user_id is not None and image.owner_user_id != user_id):
        raise NotFound("Imagem não encontrada.")
    return image


def delete_image_file(image: Image) -> None:
    try:
        image_path(image).unlink(missing_ok=True)
    except NotFound:
        pass


# --- SSRF-safe URL import ---------------------------------------------------------------


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def resolve_public_host(host: str, port: int) -> str:
    """Resolve ``host`` and return one validated public address (or raise)."""
    if not host:
        raise UnsafeUrl("URL sem host.")
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_public_address(str(literal)):
            raise UnsafeUrl("Endereços privados ou locais não são permitidos.")
        return str(literal)
    if (
        host.endswith((".local", ".internal", ".localhost", ".ts.net", ".lan", ".home"))
        or host == "localhost"
    ):
        raise UnsafeUrl("Hosts locais não são permitidos.")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrl("Não foi possível resolver o endereço da imagem.") from exc
    addresses = sorted({str(info[4][0]) for info in infos})
    if not addresses or not all(_is_public_address(a) for a in addresses):
        raise UnsafeUrl("O endereço aponta para uma rede privada ou reservada.")
    return addresses[0]


def validate_image_url(url: str) -> tuple[str, str, int, str]:
    parts = urlsplit(url.strip())
    if parts.scheme != "https":
        raise UnsafeUrl("Use um endereço https://.")
    if parts.username or parts.password:
        raise UnsafeUrl("URLs com credenciais não são permitidas.")
    host = (parts.hostname or "").lower()
    port = parts.port or 443
    if port not in (443, 8443):
        raise UnsafeUrl("Porta não permitida.")
    address = resolve_public_host(host, port)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    return host, address, port, path


def fetch_image_bytes(
    url: str, *, transport: httpx.BaseTransport | None = None
) -> tuple[bytes, str]:
    settings = get_settings()
    limit = settings.max_upload_mb * 1024 * 1024
    current = url
    with httpx.Client(timeout=10.0, follow_redirects=False, transport=transport) as client:
        for _ in range(MAX_REDIRECTS + 1):
            host, address, port, path = validate_image_url(current)
            netloc = f"[{address}]" if ":" in address else address
            pinned = f"https://{netloc}:{port}{path}"
            request = client.build_request(
                "GET",
                pinned,
                headers={"Host": host, "User-Agent": settings.http_user_agent, "Accept": "image/*"},
                extensions={"sni_hostname": host},
            )
            response = client.send(request, stream=True)
            try:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        raise UnsafeUrl("Redirecionamento inválido.")
                    current = urljoin(current, location)
                    continue
                if response.status_code != 200:
                    raise ValidationFailed(
                        f"O servidor da imagem respondeu {response.status_code}.",
                        code="image_fetch_failed",
                    )
                content_type = (
                    response.headers.get("content-type", "").split(";")[0].strip().lower()
                )
                if not content_type.startswith("image/") or "svg" in content_type:
                    raise ValidationFailed(
                        "O endereço não aponta para uma imagem suportada.", code="image_format"
                    )
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise ValidationFailed(
                            f"A imagem excede {settings.max_upload_mb} MB.", code="image_too_large"
                        )
                    chunks.append(chunk)
                return b"".join(chunks), current
            finally:
                response.close()
    raise UnsafeUrl("Redirecionamentos demais.")
