<template>
  <div class="min-h-screen w-full flex items-center justify-center px-4" style="background: var(--background-login);">
    <div class="w-full max-w-md rounded-xl border border-gray-200 bg-white/90 backdrop-blur p-6">
      <div class="flex items-center gap-3 mb-5">
        <img :src="ASSETS.logo" alt="WolfMind" class="h-7 w-7" />
        <div class="text-lg font-extrabold tracking-tight">AI 狼人杀</div>
      </div>

      <div class="flex items-center gap-4 mb-5">
        <div class="h-20 w-20 rounded-xl overflow-hidden border border-gray-200 bg-gray-50 flex items-center justify-center">
          <img v-if="avatarPreview" :src="avatarPreview" alt="avatar" class="h-full w-full object-cover" />
          <div v-else class="text-xs text-gray-500">头像</div>
        </div>
        <div class="flex-1">
          <label class="text-xs font-semibold text-gray-700">用户名</label>
          <input
            v-model="username"
            class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
            placeholder="请输入用户名"
            maxlength="20"
          />
          <div class="mt-2 flex items-center gap-2">
            <input ref="fileInput" type="file" accept="image/png,image/jpeg" class="hidden" @change="onPickFile" />
            <button
              class="rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold hover:bg-gray-50"
              type="button"
              @click="fileInput?.click()"
            >
              上传头像
            </button>
            <button
              v-if="avatarFile"
              class="rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold hover:bg-gray-50"
              type="button"
              @click="clearAvatar"
            >
              清除
            </button>
          </div>
        </div>
      </div>

      <div v-if="error" class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
        {{ error }}
      </div>

      <button
        class="w-full rounded-lg bg-black px-4 py-2.5 text-sm font-extrabold text-white disabled:bg-gray-200 disabled:text-gray-500"
        type="button"
        :disabled="loading"
        @click="start"
      >
        {{ loading ? "登录中…" : "开始游戏" }}
      </button>

      <button
        v-if="hasToken"
        class="mt-3 w-full rounded-lg border border-gray-200 px-4 py-2.5 text-sm font-extrabold text-gray-900 hover:bg-gray-50"
        type="button"
        @click="goGame"
      >
        继续游戏
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import { useRouter } from "vue-router";
import { API_URL, ASSETS } from "../config/constants";

const router = useRouter();

const username = ref("");
const avatarFile = ref(null);
const avatarPreview = ref("");
const error = ref("");
const loading = ref(false);
const fileInput = ref(null);

const hasToken = computed(() => {
  try {
    return Boolean(localStorage.getItem("wolfmind_token"));
  } catch {
  }
  try {
    return Boolean(sessionStorage.getItem("wolfmind_token"));
  } catch {
    return false;
  }
});

const clearAvatar = () => {
  avatarFile.value = null;
  avatarPreview.value = "";
  if (fileInput.value) {
    fileInput.value.value = "";
  }
};

const onPickFile = (ev) => {
  const file = ev?.target?.files?.[0] || null;
  if (!file) return;
  avatarFile.value = file;
  const url = URL.createObjectURL(file);
  avatarPreview.value = url;
};

onBeforeUnmount(() => {
  if (avatarPreview.value && String(avatarPreview.value).startsWith("blob:")) {
    URL.revokeObjectURL(avatarPreview.value);
  }
});

const saveSession = ({ token, user }) => {
  try {
    localStorage.setItem("wolfmind_token", token);
    localStorage.setItem("wolfmind_user", JSON.stringify(user || {}));
    return;
  } catch {
  }
  try {
    sessionStorage.setItem("wolfmind_token", token);
    sessionStorage.setItem("wolfmind_user", JSON.stringify(user || {}));
  } catch {
    // ignore
  }
};

const updateUser = (patch) => {
  try {
    const raw = localStorage.getItem("wolfmind_user") || "{}";
    const prev = JSON.parse(raw);
    const next = { ...(prev || {}), ...(patch || {}) };
    localStorage.setItem("wolfmind_user", JSON.stringify(next));
    return next;
  } catch {
  }
  try {
    const raw = sessionStorage.getItem("wolfmind_user") || "{}";
    const prev = JSON.parse(raw);
    const next = { ...(prev || {}), ...(patch || {}) };
    sessionStorage.setItem("wolfmind_user", JSON.stringify(next));
    return next;
  } catch {
    return patch || {};
  }
};

const start = async () => {
  if (loading.value) return;
  error.value = "";
  const name = String(username.value || "").trim();
  if (!name) {
    error.value = "请输入用户名";
    return;
  }

  loading.value = true;
  try {
    const res = await fetch(`${API_URL}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: name }),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${text || res.statusText}`.trim());
    }
    const data = await res.json();
    saveSession(data);

    const token = data?.token || "";
    if (token && avatarFile.value) {
      const form = new FormData();
      form.append("file", avatarFile.value);
      const up = await fetch(`${API_URL}/api/upload/avatar`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (up.ok) {
        const upData = await up.json().catch(() => ({}));
        const avatarUrl = upData?.avatarUrl;
        if (avatarUrl) {
          updateUser({ avatarUrl });
        }
      }
    }

    router.replace("/game");
  } catch (e) {
    error.value = String(e?.message || e);
  } finally {
    loading.value = false;
  }
};

const goGame = () => {
  router.replace("/game");
};
</script>
