import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "login",
    component: () => import("@/views/LoginView.vue"),
    meta: { layout: "bare", public: true },
  },
  {
    path: "/screen",
    name: "screen",
    component: () => import("@/views/ScreenView.vue"),
    meta: { layout: "bare", public: true },
  },
  {
    path: "/",
    name: "calendar",
    component: () => import("@/views/CalendarView.vue"),
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/",
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.token) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.token) {
    return { path: "/" };
  }
  if (auth.token && !auth.user && !to.meta.public) {
    try {
      await auth.fetchMe();
    } catch {
      /* 401 interceptor already redirects */
    }
  }
});
