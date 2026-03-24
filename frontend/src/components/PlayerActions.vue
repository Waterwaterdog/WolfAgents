<template>
  <div class="h-full flex flex-col">
    <div class="px-4 py-3 border-b border-gray-200 bg-white">
      <div class="text-xs font-extrabold tracking-wide text-gray-900">你的行动</div>
      <div v-if="turn" class="mt-1 text-[11px] text-gray-600 line-clamp-2">
        {{ turn.prompt }}
      </div>
      <div v-else class="mt-1 text-[11px] text-gray-500">等待你的行动…</div>
    </div>

    <div class="flex-1 min-h-0 overflow-auto p-4 bg-gray-50">
      <div v-if="!turn" class="text-[11px] text-gray-500">暂无待处理请求</div>

      <template v-else>
        <div class="mb-3 text-[11px] text-gray-700">
          <span class="font-extrabold">类型：</span>{{ kindLabel }}
        </div>

        <div v-if="needsChoice" class="mb-4">
          <div class="text-xs font-semibold text-gray-700 mb-2">选择目标</div>
          <div class="grid grid-cols-2 gap-2">
            <button
              v-for="c in (turn.choices || [])"
              :key="c"
              type="button"
              class="rounded-lg border px-3 py-2 text-xs font-semibold"
              :class="target === c ? 'border-black bg-black text-white' : 'border-gray-200 bg-white text-gray-900 hover:bg-gray-50'"
              @click="target = c"
            >
              {{ c }}
            </button>
          </div>
        </div>

        <div v-if="turn.kind === 'witch_resurrect'" class="mb-4">
          <div class="text-xs font-semibold text-gray-700 mb-2">是否使用解药</div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="rounded-lg border px-3 py-2 text-xs font-semibold"
              :class="resurrect === true ? 'border-black bg-black text-white' : 'border-gray-200 bg-white text-gray-900 hover:bg-gray-50'"
              @click="resurrect = true"
            >
              是
            </button>
            <button
              type="button"
              class="rounded-lg border px-3 py-2 text-xs font-semibold"
              :class="resurrect === false ? 'border-black bg-black text-white' : 'border-gray-200 bg-white text-gray-900 hover:bg-gray-50'"
              @click="resurrect = false"
            >
              否
            </button>
          </div>
        </div>

        <div v-if="turn.kind === 'witch_poison'" class="mb-4">
          <label class="flex items-center gap-2 text-xs font-semibold text-gray-700">
            <input v-model="poison" type="checkbox" />
            使用毒药
          </label>
        </div>

        <div v-if="turn.kind === 'hunter_shoot'" class="mb-4">
          <label class="flex items-center gap-2 text-xs font-semibold text-gray-700">
            <input v-model="shoot" type="checkbox" />
            开枪
          </label>
        </div>

        <div v-if="needsSpeech" class="mb-4">
          <div class="text-xs font-semibold text-gray-700 mb-2">发言</div>
          <textarea
            v-model="speech"
            class="w-full rounded-lg border border-gray-200 px-3 py-2 text-xs outline-none focus:border-gray-400 min-h-[110px]"
            placeholder="输入你的发言…"
          />
        </div>

        <button
          type="button"
          class="w-full rounded-lg bg-black px-4 py-2.5 text-sm font-extrabold text-white disabled:bg-gray-200 disabled:text-gray-500"
          :disabled="submitting || !canSubmit"
          @click="submit"
        >
          {{ submitting ? "提交中…" : "提交" }}
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  turn: { type: Object, default: null },
  onSubmit: { type: Function, default: null },
});

const submitting = ref(false);
const target = ref("");
const speech = ref("");
const resurrect = ref(null);
const poison = ref(false);
const shoot = ref(false);

watch(
  () => props.turn?.requestId,
  () => {
    target.value = "";
    speech.value = "";
    resurrect.value = null;
    poison.value = false;
    shoot.value = false;
  }
);

const kindLabel = computed(() => {
  const k = props.turn?.kind;
  if (k === "vote") return "投票";
  if (k === "select") return "选择目标";
  if (k === "witch_resurrect") return "女巫解药";
  if (k === "witch_poison") return "女巫毒药";
  if (k === "hunter_shoot") return "猎人开枪";
  return "发言";
});

const needsChoice = computed(() => {
  const k = props.turn?.kind;
  if (k === "vote" || k === "select") return true;
  if (k === "witch_poison") return poison.value;
  if (k === "hunter_shoot") return shoot.value;
  return false;
});

const needsSpeech = computed(() => {
  const k = props.turn?.kind;
  return k === "speech" || k === "vote" || k === "select";
});

const canSubmit = computed(() => {
  if (!props.turn?.requestId) return false;
  const k = props.turn?.kind;
  if (k === "witch_resurrect") return resurrect.value !== null;
  if (k === "witch_poison") return !poison.value || Boolean(target.value);
  if (k === "hunter_shoot") return !shoot.value || Boolean(target.value);
  if (k === "vote" || k === "select") return Boolean(target.value);
  return Boolean(String(speech.value || "").trim());
});

const submit = async () => {
  if (!props.turn || !props.onSubmit || submitting.value || !canSubmit.value) return;
  submitting.value = true;
  try {
    const payload = {
      requestId: props.turn.requestId,
      speech: String(speech.value || ""),
      target: target.value || null,
      resurrect: resurrect.value,
      poison: poison.value,
      shoot: shoot.value,
    };
    await Promise.resolve(props.onSubmit(payload));
  } finally {
    submitting.value = false;
  }
};
</script>

