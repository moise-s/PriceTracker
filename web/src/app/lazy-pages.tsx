import { lazy } from "react";

// Route-level code splitting for the heavier screens.
export const AdminPage = lazy(() => import("@/pages/admin").then((m) => ({ default: m.AdminPage })));
export const ComparePage = lazy(() => import("@/pages/compare").then((m) => ({ default: m.ComparePage })));
export const HistoryPage = lazy(() => import("@/pages/history").then((m) => ({ default: m.HistoryPage })));
export const ProductFormPage = lazy(() => import("@/pages/product-form").then((m) => ({ default: m.ProductFormPage })));
export const ProfilePage = lazy(() => import("@/pages/profile").then((m) => ({ default: m.ProfilePage })));
export const SchedulesPage = lazy(() => import("@/pages/schedules").then((m) => ({ default: m.SchedulesPage })));
