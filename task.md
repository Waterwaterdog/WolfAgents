# AI 狼人杀 - 真人玩家接入与 UI 优化任务清单

## 项目概述
当前项目是 9 个 AI agent 进行狼人杀对战的游戏系统。本任务计划将其改造为：**1 个真人玩家 + 8 个 AI 玩家**的混合模式，并添加完整的用户界面系统。

---

## 📋 任务分解

### 阶段一：项目分析与设计（建议耗时：1-2 小时）

#### 1.1 理解现有架构
- [ ] 阅读 `backend/main.py` - 游戏入口
- [ ] 阅读 `backend/core/game_engine.py` - 游戏核心引擎（第 393-420 行是角色分配逻辑）
- [ ] 阅读 `backend/models/roles.py` - 角色定义
- [ ] 阅读 `frontend/src/App.vue` - 前端主界面
- [ ] 阅读 `backend/api_server.py` - API 服务器

#### 1.2 技术选型决策
- [ ] **前端框架**：继续使用 Vue3 + Vite（已有基础）
- [ ] **UI 组件库**：建议使用 Element Plus 或保持现有 TailwindCSS
- [ ] **状态管理**：Pinia（轻量级）或 Vue Reactivity
- [ ] **图片上传**：前端处理 + 后端存储到 `static/avatars/` 目录
- [ ] **会话管理**：基于 WebSocket 或 JWT Token

---

### 阶段二：后端改造（建议耗时：6-8 小时）

#### 2.1 修改角色分配逻辑
**文件**: `backend/core/game_engine.py`（约第 393 行）

**当前逻辑**：
```python
roles = ["werewolf"] * 3 + ["villager"] * 3 + ["seer", "witch", "hunter"]
np.random.shuffle(agents)
np.random.shuffle(roles)
```

**需要修改为**：
- [ ] 支持 9 人局（1 真人 + 8 AI）或保持 9AI 可选
- [ ] 角色随机分配逻辑保持不变
- [ ] 增加真人玩家标识字段
- [ ] 确保真人玩家也能收到角色信息

#### 2.2 创建用户系统
**新文件**: `backend/models/user.py`
- [ ] 用户数据模型（用户名、头像路径、游戏历史）
- [ ] 用户认证（简单密码或免密登录）
- [ ] 用户会话管理

**新文件**: `backend/api/auth.py`
- [ ] 登录接口 `POST /api/login`
- [ ] 登出接口 `POST /api/logout`
- [ ] 获取当前用户信息 `GET /api/user`

#### 2.3 修改游戏服务
**文件**: `backend/game_service.py`

- [ ] 支持真人玩家加入游戏
- [ ] 真人玩家的输入处理（讨论发言、投票、夜间行动）
- [ ] WebSocket 消息推送（游戏状态实时更新）

**新增 WebSocket 事件**：
```python
# 客户端 -> 服务器
"player_action"      # 真人玩家行动（发言/投票/技能）
"player_ready"       # 玩家准备就绪
"submit_discussion"  # 提交讨论发言
"submit_vote"        # 提交投票
"submit_night_action" # 提交夜间行动

# 服务器 -> 客户端
"game_state_update"  # 游戏状态更新
"your_role"          # 告知玩家身份
"your_turn"          # 轮到玩家行动
"game_result"        # 游戏结果
```

#### 2.4 头像上传功能
**新文件**: `backend/api/upload.py`

- [ ] 头像上传接口 `POST /api/upload/avatar`
- [ ] 图片验证（格式、大小限制）
- [ ] 存储到 `static/avatars/{user_id}_{timestamp}.jpg`
- [ ] 返回头像 URL

---

### 阶段三：前端开发（建议耗时：10-12 小时）

#### 3.1 创建登录界面
**新文件**: `frontend/src/components/LoginView.vue`

**功能需求**：
- [ ] 用户名输入框
- [ ] 头像预览区域（支持上传/默认头像）
- [ ] 头像上传按钮（调用 `/api/upload/avatar`）
- [ ] 登录按钮
- [ ] 错误提示

**UI 设计建议**：
```
┌─────────────────────────────────────┐
│         🐺 AI 狼人杀                │
│                                     │
│    ┌─────────────────────────┐     │
│    │   [头像预览/上传区域]    │     │
│    │      📷 上传头像         │     │
│    └─────────────────────────┘     │
│                                     │
│    用户名：[____________]           │
│                                     │
│       [开始游戏]                    │
│                                     │
└─────────────────────────────────────┘
```

#### 3.2 修改主游戏界面
**文件**: `frontend/src/App.vue`

- [ ] 添加用户信息显示（头像 + 用户名）
- [ ] 区分真人玩家和 AI 玩家的显示样式
- [ ] 真人玩家操作面板（发言输入框、投票按钮等）
- [ ] 游戏状态提示（"等待你的行动"、"夜晚请闭眼"等）

#### 3.3 创建玩家操作组件
**新文件**: `frontend/src/components/PlayerActions.vue`

**功能**：
- [ ] 讨论阶段：文本输入框 + 发送按钮
- [ ] 投票阶段：玩家列表单选 + 确认投票
- [ ] 夜间行动：根据角色显示不同操作
  - 狼人：选择击杀目标
  - 预言家：选择查验目标
  - 女巫：选择使用解药/毒药
  - 猎人：死亡时选择开枪目标

#### 3.4 路由与导航
**文件**: `frontend/src/main.js`

- [ ] 添加 Vue Router
- [ ] 配置路由：
  - `/login` - 登录页
  - `/game` - 游戏主界面
  - `/history` - 游戏历史（可选）
- [ ] 路由守卫（未登录跳转到登录页）

---

### 阶段四：背景图片系统（建议耗时：2-3 小时）

#### 4.1 背景图片目录结构
创建以下目录：
```
static/
├── backgrounds/
│   ├── day_default.jpg        # 默认白天背景
│   ├── night_default.jpg      # 默认夜晚背景
│   ├── login_default.jpg      # 默认登录页背景
│   └── user_custom/           # 用户自定义背景
│       ├── day_custom.jpg
│       ├── night_custom.jpg
│       └── login_custom.jpg
```

#### 4.2 后端背景配置
**新文件**: `backend/api/backgrounds.py`

- [ ] 获取背景图片接口 `GET /api/backgrounds/{type}`
  - `type`: `day`, `night`, `login`
- [ ] 上传自定义背景 `POST /api/backgrounds/upload`
- [ ] 背景图片配置存储在 `config.py`

#### 4.3 前端背景切换
**文件**: `frontend/src/styles/global.css` 或 `frontend/src/App.vue`

**CSS 变量方式**：
```css
:root {
  --background-day: url('/static/backgrounds/day_default.jpg');
  --background-night: url('/static/backgrounds/night_default.jpg');
  --background-login: url('/static/backgrounds/login_default.jpg');
}

.game-container {
  background-image: var(--background-day); /* 或 var(--background-night) */
  background-size: cover;
  background-position: center;
}
```

**动态切换逻辑**：
```javascript
// 根据游戏阶段切换背景
watch(() => gamePhase.value, (newPhase) => {
  if (newPhase === 'night') {
    document.documentElement.style.setProperty(
      '--current-background',
      'var(--background-night)'
    );
  } else {
    document.documentElement.style.setProperty(
      '--current-background',
      'var(--background-day)'
    );
  }
});
```

#### 4.4 用户自定义背景功能
**前端组件**: `frontend/src/components/BackgroundSettings.vue`

- [ ] 背景图片预览
- [ ] 上传按钮（调用 `/api/backgrounds/upload`）
- [ ] 重置为默认背景
- [ ] 实时预览效果

---

### 阶段五：联调与测试（建议耗时：4-6 小时）

#### 5.1 端到端测试流程
- [ ] 用户登录流程
- [ ] 头像上传与显示
- [ ] 游戏开始 → 角色分配 → 真人玩家收到角色
- [ ] 白天讨论：真人玩家发言 → AI 玩家看到发言
- [ ] 投票阶段：真人玩家投票 → 计票逻辑
- [ ] 夜间行动：根据角色执行技能
- [ ] 游戏结束 → 结果显示

#### 5.2 边界情况测试
- [ ] 网络断开重连
- [ ] 玩家超时未操作（AI 托管或判负）
- [ ] 头像上传失败处理
- [ ] 背景图片格式错误处理

#### 5.3 性能优化
- [ ] WebSocket 消息压缩
- [ ] 图片懒加载
- [ ] 背景图片预加载

---

## 📁 文件清单

### 需要新建的文件
```
backend/
├── models/
│   └── user.py                    # 用户模型
├── api/
│   ├── auth.py                    # 认证接口
│   ├── upload.py                  # 上传接口
│   └── backgrounds.py             # 背景管理接口
└── services/
    └── user_service.py            # 用户服务

frontend/
├── src/
│   ├── components/
│   │   ├── LoginView.vue          # 登录界面
│   │   ├── PlayerActions.vue      # 玩家操作面板
│   │   └── BackgroundSettings.vue # 背景设置
│   ├── router/
│   │   └── index.js               # 路由配置
│   └── stores/
│       └── user.js                # 用户状态管理 (Pinia)
│
static/
├── backgrounds/
│   ├── day_default.jpg
│   ├── night_default.jpg
│   └── login_default.jpg
└── avatars/                        # 用户头像存储
    └── default.png
```

### 需要修改的文件
```
backend/
├── core/
│   └── game_engine.py             # 角色分配逻辑
├── game_service.py                # 游戏服务
├── api_server.py                  # API 路由
└── config.py                      # 配置项

frontend/
├── src/
│   ├── App.vue                    # 主界面
│   ├── main.js                    # 添加路由
│   └── components/
│       └── RoomView.vue           # 可能需调整
```

---

## 🎨 背景图片更换指南

### 方法一：直接替换文件（推荐新手）
1. 准备图片文件（建议尺寸：1920x1080，格式：JPG/PNG）
2. 复制到对应目录：
   - 白天背景：`static/backgrounds/day_default.jpg`
   - 夜晚背景：`static/backgrounds/night_default.jpg`
   - 登录背景：`static/backgrounds/login_default.jpg`
3. 刷新页面即可看到效果

### 方法二：通过设置界面上传
1. 在游戏界面点击右上角设置图标
2. 选择"背景设置"
3. 点击"上传背景图片"
4. 选择本地图片文件
5. 预览并确认

### 方法三：代码配置（高级）
修改 `frontend/src/App.vue` 中的背景配置：
```javascript
const backgroundConfig = {
  day: '/static/backgrounds/my_custom_day.jpg',
  night: '/static/backgrounds/my_custom_night.jpg',
  login: '/static/backgrounds/my_custom_login.jpg',
};
```

---

## 🔧 开发环境配置

### 前端开发
```bash
cd frontend
npm install
npm run dev
```

### 后端开发
```bash
cd backend
uv sync
uv run uvicorn api_server:app --reload
```

### 同时启动前后端
```bash
npm run dev
```

---

## 📝 开发建议

### 优先级建议
1. **P0（必须完成）**:
   - 登录界面
   - 角色分配给真人玩家
   - 真人玩家发言/投票功能
   - 基础背景切换

2. **P1（重要）**:
   - 头像上传
   - 夜间行动 UI
   - 游戏历史记录

3. **P2（可选）**:
   - 自定义背景上传
   - 游戏回放功能
   - 玩家统计面板

### 技术债务预防
- [ ] 所有 API 添加错误处理
- [ ] 前端组件添加 loading 状态
- [ ] 关键操作添加确认提示
- [ ] 代码添加注释（尤其是游戏逻辑）

---

## 🎯 验收标准

### 功能验收
- [ ] 用户可以成功登录
- [ ] 用户可以上传头像
- [ ] 游戏开始时，真人玩家随机获得身份牌
- [ ] 真人玩家可以参与讨论、投票、夜间行动
- [ ] 游戏界面根据白天/夜晚切换背景
- [ ] 用户可以自定义背景图片

### 体验验收
- [ ] 登录流程顺畅（<3 秒）
- [ ] 游戏操作响应及时（<1 秒）
- [ ] 界面美观，无明显 UI 问题
- [ ] 错误提示清晰友好

---

## 📚 参考资料

### 项目文档
- [README.md](README.md) - 项目说明
- [backend/core/game_engine.py](backend/core/game_engine.py) - 游戏引擎实现

### 技术文档
- [Vue3 官方文档](https://vuejs.org/)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [AgentScope 文档](https://github.com/modelscope/agentscope)

---

## 📞 常见问题

### Q1: 如何测试真人玩家功能？
A: 可以先在后端添加一个测试接口，直接返回指定角色给真人玩家，验证前端逻辑后再集成随机分配。

### Q2: 头像上传失败怎么办？
A: 检查：
1. `static/avatars/` 目录是否存在
2. 文件权限是否正确
3. 图片格式是否支持（建议仅支持 JPG/PNG）
4. 文件大小限制（建议<5MB）

### Q3: 背景图片不显示？
A: 检查：
1. 图片路径是否正确（注意相对路径 vs 绝对路径）
2. CSS 是否正确加载
3. 浏览器控制台是否有 404 错误

---

**最后更新**: 2026-03-23  
**版本**: v1.0  
**状态**: 待开始