import { createRouter, createWebHistory } from "vue-router";
import LoginView from "../views/LoginView.vue";
import GameView from "../views/GameView.vue";

const getToken = () => {
  try {
    const v = localStorage.getItem("wolfmind_token");
    if (v) return v;
  } catch {
  }
  try {
    return sessionStorage.getItem("wolfmind_token") || "";
  } catch {
    return "";
  }
};

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/game" },
    { path: "/login", component: LoginView, meta: { public: true } },
    { path: "/game", component: GameView },
  ],
});

router.beforeEach((to) => {
  if (to.meta && to.meta.public) {
    return true;
  }
  const token = getToken();
  if (!token) {
    return "/login";
  }
  return true;
});
