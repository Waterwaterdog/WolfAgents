<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <div
      style="
        flex-shrink: 0;
        padding: 14px 16px;
        background: #ffffff;
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        align-items: center;
        justify-content: space-between;
      "
    >
      <div style="font-size: 14px; font-weight: 800; letter-spacing: 1px; color: #111827;">
        游戏记录
      </div>
      <div style="font-size: 12px; color: #6b7280;">
        {{ messages.length }} 条
      </div>
    </div>

    <div
      ref="containerRef"
      class="feed-content"
      style="
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        padding: 12px;
        background: #f5f5f5;
      "
    >
      <div v-if="messages.length === 0" style="color: #6b7280; padding: 8px 4px; font-size: 13px;">
        等待事件…
      </div>
      <div v-else>
        <div
          v-for="m in messages"
          :key="m.id"
          :id="`feed-item-${m.id}`"
          :style="{
            border: '1px solid #e5e7eb',
            borderLeft: `4px solid ${getMessageStyle(m).borderColor}`,
            background: highlightId === m.id ? '#fff7ed' : getMessageStyle(m).bgColor,
            padding: '12px 12px',
            marginBottom: '10px',
            borderRadius: '4px',
          }"
        >
          <div style="display: flex; justify-content: space-between; gap: 8px; margin-bottom: 8px;">
            <div :style="{ fontSize: '13px', fontWeight: 800, color: getMessageStyle(m).labelColor }">
              {{ isSystemMessage(m) ? '系统' : (m.agent || '玩家') }}
              <span
                v-if="!isSystemMessage(m) && displayRole(m)"
                style="color: #9ca3af; font-weight: 600;"
              >
                · {{ displayRole(m) }}
              </span>
            </div>
            <div style="font-size: 11px; color: #9ca3af;">
              {{ formatTime(m.timestamp) }}
            </div>
          </div>
          <div>
            <div v-if="!hasStructured(m)"
              :style="{
                fontSize: '13px',
                color: getMessageStyle(m).textColor,
                whiteSpace: 'pre-wrap',
                lineHeight: 1.7,
                wordBreak: 'break-word',
                overflowWrap: 'anywhere',
              }"
            >
              {{ m.content }}
            </div>
            <div v-else style="display: flex; flex-direction: column; gap: 8px;">
              <div
                v-if="canShowThought(m)"
                style="font-size: 13px; color: #6b7280; white-space: pre-wrap; line-height: 1.7; overflow-wrap: anywhere;"
              >
                <span style="font-weight: 700; color: #9ca3af;">心声：</span>{{ m.thought }}
              </div>
              <div
                v-if="canShowBehavior(m)"
                :style="{
                  fontSize: '13px',
                  color: getMessageStyle(m).textColor,
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.7,
                  overflowWrap: 'anywhere'
                }"
              >
                <span style="font-weight: 700; color: #7c73e6;">表现：</span>{{ m.behavior }}
              </div>
              <div
                v-if="m.speech"
                :style="{
                  fontSize: '13px',
                  color: getMessageStyle(m).textColor,
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.7,
                  overflowWrap: 'anywhere'
                }"
              >
                <span style="font-weight: 700; color: #5b52cc;">发言：</span>{{ m.speech }}
              </div>
              <div
                v-if="!m.speech && m.content"
                :style="{
                  fontSize: '13px',
                  color: getMessageStyle(m).textColor,
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.7,
                  overflowWrap: 'anywhere'
                }"
              >
                {{ m.content }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineExpose, ref } from "vue";

const props = defineProps({
  feed: { type: Array, default: () => [] },
  viewerAgentId: { type: String, default: "" },
  viewerAlignment: { type: String, default: "unknown" },
  werewolfTeamIds: { type: [Array, Object], default: () => [] },
  isReviewMode: { type: Boolean, default: false },
});

const containerRef = ref(null);
const highlightId = ref(null);

const formatTime = (ts) => {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

const MESSAGE_STYLES = {
  system: {
    borderColor: "#6b7280",
    bgColor: "#f9fafb",
    labelColor: "#4b5563",
    textColor: "#374151",
  },
  gamePhase: {
    borderColor: "#64748b",
    bgColor: "#f8fafc",
    labelColor: "#475569",
    textColor: "#334155",
  },
  player: {
    borderColor: "#7c73e6",
    bgColor: "#fafaff",
    labelColor: "#5b52cc",
    textColor: "#1f2937",
  },
};

const isGamePhaseMessage = (content) => {
  if (!content) return false;
  const text = String(content);
  const phasePatterns = [
    /第\s*\d+\s*回合/,
    /夜晚阶段/,
    /白天阶段/,
    /游戏开始/,
    /游戏结束/,
    /投票阶段/,
    /讨论阶段/,
    /天亮了/,
    /请.*睁眼/,
    /请.*闭眼/,
    /被淘汰/,
    /出局/,
    /平安夜/,
    /狼人.*请/,
    /预言家.*请/,
    /女巫.*请/,
    /猎人.*请/,
    /守卫.*请/,
  ];
  return phasePatterns.some((pattern) => pattern.test(text));
};

const getMessageStyle = (m) => {
  const isSystem = m.agent === "System" || m.role === "System";
  if (isSystem) {
    if (isGamePhaseMessage(m.content)) {
      return MESSAGE_STYLES.gamePhase;
    }
    return MESSAGE_STYLES.system;
  }
  return MESSAGE_STYLES.player;
};

const normalizeFeedToMessages = (feed) => {
  const out = [];
  for (const item of feed || []) {
    if (!item) continue;

    if (item.type === "conference" && item.data?.messages) {
      for (const msg of item.data.messages) {
        out.push({
          id: msg.id,
          timestamp: msg.timestamp,
          agent: msg.agent,
          role: msg.role,
          content: msg.content,
          agentId: msg.agentId,
          thought: msg.thought,
          behavior: msg.behavior,
          speech: msg.speech,
          category: msg.category,
          action: msg.action,
        });
      }
      continue;
    }

    if (item.type === "message" && item.data) {
      out.push({
        id: item.id,
        timestamp: item.data.timestamp,
        agent: item.data.agent,
        role: item.data.role,
        content: item.data.content,
        agentId: item.data.agentId,
        thought: item.data.thought,
        behavior: item.data.behavior,
        speech: item.data.speech,
        category: item.data.category,
        action: item.data.action,
      });
      continue;
    }

    if (item.type === "memory" && item.data) {
      out.push({
        id: item.id,
        timestamp: item.data.timestamp,
        agent: item.data.agent,
        role: "记忆",
        content: item.data.content,
        agentId: item.data.agentId,
      });
    }
  }
  return out;
};

const messages = computed(() => normalizeFeedToMessages(props.feed));

const werewolfTeamSet = computed(() => {
  const v = props.werewolfTeamIds;
  if (v && typeof v === "object" && typeof v.has === "function") return v;
  if (Array.isArray(v)) return new Set(v.map((x) => String(x || "")).filter(Boolean));
  return new Set();
});

const canShowThought = (m) => {
  if (!m || !m.thought) return false;
  if (props.isReviewMode) return true;
  if (props.viewerAlignment !== "werewolves") return false;
  const agentId = String(m.agentId || "");
  return werewolfTeamSet.value.has(agentId);
};

const canShowBehavior = (m) => {
  if (!m || !m.behavior) return false;
  if (props.isReviewMode) return true;
  if (props.viewerAlignment !== "werewolves") return false;
  const agentId = String(m.agentId || "");
  return werewolfTeamSet.value.has(agentId);
};

const displayRole = (m) => {
  if (!m || !m.role) return "";
  if (props.isReviewMode) return String(m.role || "");
  const agentId = String(m.agentId || "");
  if (agentId && props.viewerAgentId && agentId === props.viewerAgentId) return String(m.role || "");
  return "";
};

const hasStructured = (m) => {
  const thought = canShowThought(m) ? String(m.thought || "").trim() : "";
  const behavior = canShowBehavior(m) ? String(m.behavior || "").trim() : "";
  const speech = String(m.speech || "").trim();
  return Boolean(thought || behavior || speech);
};

const isSystemMessage = (m) => m.agent === "System" || m.role === "System";

const scrollToMessage = (bubble) => {
  const id = bubble?.feedItemId || bubble?.id;
  if (!id) return;
  const el = document.getElementById(`feed-item-${id}`);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    highlightId.value = id;
    setTimeout(() => {
      highlightId.value = null;
    }, 1600);
  }
};

defineExpose({ scrollToMessage });
</script>
