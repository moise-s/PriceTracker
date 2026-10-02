import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, errorMessage, type Schemas, unwrap } from "./client";

export const keys = {
  meta: ["meta"] as const,
  me: ["me"] as const,
  catalog: ["catalog"] as const,
  products: ["products"] as const,
  lists: ["lists"] as const,
  markets: ["markets"] as const,
  profile: ["profile"] as const,
  addresses: ["addresses"] as const,
  vehicles: ["vehicles"] as const,
  runs: ["runs"] as const,
  run: (id: string) => ["runs", id] as const,
  activeRun: ["runs", "active"] as const,
  comparison: (params: object) => ["comparison", params] as const,
  history: (productId: string, days: number) => ["history", productId, days] as const,
  schedules: ["schedules"] as const,
  sessions: ["sessions"] as const,
  admin: ["admin"] as const,
  alerts: ["alerts"] as const,
  notifications: ["notifications"] as const,
};

function onMutationError(error: unknown) {
  toast.error(errorMessage(error));
}

// --- session ------------------------------------------------------------------------------------

export function useMeta() {
  return useQuery({ queryKey: keys.meta, queryFn: () => unwrap(api.GET("/api/v1/meta")), staleTime: 60_000 });
}

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return await unwrap(api.GET("/api/v1/auth/me"));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 30_000,
    retry: false,
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/logout")),
    onSettled: () => {
      client.clear();
      window.location.assign("/entrar");
    },
  });
}

// --- catalog, products, lists -----------------------------------------------------------------------

export function useCatalog() {
  return useQuery({ queryKey: keys.catalog, queryFn: () => unwrap(api.GET("/api/v1/catalog")) });
}

export function useProducts() {
  return useQuery({ queryKey: keys.products, queryFn: () => unwrap(api.GET("/api/v1/products")) });
}

export function usePersonalizeProduct() {
  const client = useQueryClient();
  const invalidate = useInvalidateListData();
  return useMutation({
    mutationFn: (catalogItemId: string) => unwrap(api.POST("/api/v1/products/from-catalog/{catalog_item_id}", { params: { path: { catalog_item_id: catalogItemId } } })),
    onSuccess: (product) => {
      client.setQueryData<Schemas["ProductOut"][]>(keys.products, (current) => [...(current ?? []).filter((p) => p.id !== product.id), product]);
      invalidate();
    },
    onError: onMutationError,
  });
}

export function useLists() {
  return useQuery({ queryKey: keys.lists, queryFn: () => unwrap(api.GET("/api/v1/lists")) });
}

export function useDefaultList() {
  const lists = useLists();
  const list = lists.data?.find((l) => l.is_default) ?? lists.data?.[0];
  return { ...lists, list };
}

function useInvalidateListData() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: keys.lists });
    void client.invalidateQueries({ queryKey: keys.catalog });
    void client.invalidateQueries({ queryKey: keys.products });
    void client.invalidateQueries({ queryKey: ["comparison"] });
  };
}

export function useAddToList() {
  const invalidate = useInvalidateListData();
  return useMutation({
    mutationFn: ({ listId, body }: { listId: string; body: Schemas["ListItemIn"] }) =>
      unwrap(api.POST("/api/v1/lists/{list_id}/items", { params: { path: { list_id: listId } }, body })),
    onSuccess: invalidate,
    onError: onMutationError,
  });
}

export function useUpdateListItem() {
  const invalidate = useInvalidateListData();
  return useMutation({
    mutationFn: ({ listId, itemId, body }: { listId: string; itemId: string; body: Schemas["ListItemPatch"] }) =>
      unwrap(api.PATCH("/api/v1/lists/{list_id}/items/{item_id}", { params: { path: { list_id: listId, item_id: itemId } }, body })),
    onSuccess: invalidate,
    onError: onMutationError,
  });
}

export function useRemoveListItem() {
  const invalidate = useInvalidateListData();
  return useMutation({
    mutationFn: ({ listId, itemId }: { listId: string; itemId: string }) =>
      unwrap(api.DELETE("/api/v1/lists/{list_id}/items/{item_id}", { params: { path: { list_id: listId, item_id: itemId } } })),
    onSuccess: invalidate,
    onError: onMutationError,
  });
}

export function useSaveProduct() {
  const invalidate = useInvalidateListData();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["ProductIn"] | Schemas["ProductPatch"] }) =>
      id
        ? unwrap(api.PATCH("/api/v1/products/{product_id}", { params: { path: { product_id: id } }, body: body as Schemas["ProductPatch"] }))
        : unwrap(api.POST("/api/v1/products", { body: body as Schemas["ProductIn"] })),
    onSuccess: invalidate,
    onError: onMutationError,
  });
}

export function useDeleteProduct() {
  const invalidate = useInvalidateListData();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/products/{product_id}", { params: { path: { product_id: id } } })),
    onSuccess: invalidate,
    onError: onMutationError,
  });
}

// --- markets & profile ---------------------------------------------------------------------------------

export function useMarkets() {
  return useQuery({ queryKey: keys.markets, queryFn: () => unwrap(api.GET("/api/v1/markets")) });
}

export function useSaveStores() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (selections: Schemas["StoreSelectionIn"][]) => unwrap(api.PUT("/api/v1/me/stores", { body: { selections } })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.markets });
      void client.invalidateQueries({ queryKey: ["comparison"] });
    },
    onError: onMutationError,
  });
}

export function useProfile() {
  return useQuery({ queryKey: keys.profile, queryFn: () => unwrap(api.GET("/api/v1/me/profile")) });
}

export function useUpdateProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["ProfilePatch"]) => unwrap(api.PATCH("/api/v1/me/profile", { body })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.profile });
      void client.invalidateQueries({ queryKey: keys.me });
      void client.invalidateQueries({ queryKey: ["comparison"] });
    },
    onError: onMutationError,
  });
}

export function useAddresses() {
  return useQuery({ queryKey: keys.addresses, queryFn: () => unwrap(api.GET("/api/v1/me/addresses")) });
}

export function useVehicles() {
  return useQuery({ queryKey: keys.vehicles, queryFn: () => unwrap(api.GET("/api/v1/me/vehicles")) });
}

export function useSaveAddress() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["AddressIn"] }) =>
      id
        ? unwrap(api.PUT("/api/v1/me/addresses/{address_id}", { params: { path: { address_id: id } }, body }))
        : unwrap(api.POST("/api/v1/me/addresses", { body })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.addresses });
      void client.invalidateQueries({ queryKey: keys.markets });
      void client.invalidateQueries({ queryKey: ["comparison"] });
    },
    onError: onMutationError,
  });
}

export function useSaveVehicle() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Schemas["VehicleIn"] }) =>
      id
        ? unwrap(api.PUT("/api/v1/me/vehicles/{vehicle_id}", { params: { path: { vehicle_id: id } }, body }))
        : unwrap(api.POST("/api/v1/me/vehicles", { body })),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.vehicles });
      void client.invalidateQueries({ queryKey: ["comparison"] });
    },
    onError: onMutationError,
  });
}

// --- runs, comparison, history ------------------------------------------------------------------------------

export function useActiveRun() {
  return useQuery({
    queryKey: keys.activeRun,
    queryFn: () => unwrap(api.GET("/api/v1/runs/active")),
    refetchInterval: (query) => (query.state.data ? 2000 : 15000),
  });
}

export function useRuns() {
  return useQuery({ queryKey: keys.runs, queryFn: () => unwrap(api.GET("/api/v1/runs", { params: { query: { limit: 10 } } })) });
}

export function useRun(id: string | undefined) {
  const client = useQueryClient();
  return useQuery({
    queryKey: keys.run(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const run = await unwrap(api.GET("/api/v1/runs/{run_id}", { params: { path: { run_id: id! } } }));
      if (!["queued", "running"].includes(run.status)) {
        void client.invalidateQueries({ queryKey: ["comparison"] });
        void client.invalidateQueries({ queryKey: keys.activeRun });
        void client.invalidateQueries({ queryKey: keys.markets });
        void client.invalidateQueries({ queryKey: keys.alerts });
        void client.invalidateQueries({ queryKey: keys.notifications });
      }
      return run;
    },
    refetchInterval: (query) => (query.state.data && ["queued", "running"].includes(query.state.data.status) ? 1500 : false),
  });
}

export function useStartRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["RunCreateIn"]) => unwrap(api.POST("/api/v1/runs", { body })),
    onSuccess: (run) => {
      client.setQueryData(keys.run(run.id), run);
      void client.invalidateQueries({ queryKey: keys.activeRun });
      void client.invalidateQueries({ queryKey: keys.runs });
    },
  });
}

export function useCancelRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.POST("/api/v1/runs/{run_id}/cancel", { params: { path: { run_id: id } } })),
    onSuccess: (run) => {
      client.setQueryData(keys.run(run.id), run);
      void client.invalidateQueries({ queryKey: keys.activeRun });
    },
    onError: onMutationError,
  });
}

export function useRetryRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.POST("/api/v1/runs/{run_id}/retry", { params: { path: { run_id: id } } })),
    onSuccess: (run) => {
      client.setQueryData(keys.run(run.id), run);
      void client.invalidateQueries({ queryKey: keys.activeRun });
    },
    onError: onMutationError,
  });
}

export interface ComparisonParams {
  allow_stale?: boolean;
  include_travel?: boolean;
  max_stops?: number;
}

export function useComparison(params: ComparisonParams = {}) {
  return useQuery({
    queryKey: keys.comparison(params),
    queryFn: () => unwrap(api.GET("/api/v1/comparison", { params: { query: params } })),
    placeholderData: keepPreviousData,
  });
}

export function useHistory(productId: string | undefined, days: number) {
  return useQuery({
    queryKey: keys.history(productId ?? "", days),
    enabled: Boolean(productId),
    queryFn: () => unwrap(api.GET("/api/v1/history/products/{product_id}", { params: { path: { product_id: productId! }, query: { days } } })),
  });
}

// --- price alerts & notifications ---------------------------------------------------------------

export function useAlerts() {
  return useQuery({ queryKey: keys.alerts, queryFn: () => unwrap(api.GET("/api/v1/alerts")) });
}

export function useSetAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ productId, body }: { productId: string; body: Schemas["AlertIn"] }) =>
      unwrap(api.PUT("/api/v1/products/{product_id}/alert", { params: { path: { product_id: productId } }, body })),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.alerts }),
    onError: onMutationError,
  });
}

export function useDeleteAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (productId: string) => unwrap(api.DELETE("/api/v1/products/{product_id}/alert", { params: { path: { product_id: productId } } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.alerts }),
    onError: onMutationError,
  });
}

export function useNotifications() {
  return useQuery({ queryKey: keys.notifications, queryFn: () => unwrap(api.GET("/api/v1/notifications")), refetchInterval: 60_000 });
}

export function useMarkNotificationsRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (ids?: string[]) => unwrap(api.POST("/api/v1/notifications/read", { body: { ids: ids ?? null } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.notifications }),
    onError: onMutationError,
  });
}
