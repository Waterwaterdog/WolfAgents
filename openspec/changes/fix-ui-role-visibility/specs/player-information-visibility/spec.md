## ADDED Requirements

### Requirement: Player can see own role card at round start
在每一轮开始时，系统 MUST 让玩家获取并可见“自己本轮的身份牌”，且该身份信息在本轮对局阶段内对自己始终可见。

#### Scenario: Self role is available from the beginning of the round
- **WHEN** 新的一轮开始并进入对局阶段界面
- **THEN** 当前玩家可以看到自己的本轮身份牌信息，且不会显示为“未知”

### Requirement: Public speech is visible to all players during the match
在非复盘阶段，对局内所有玩家 MUST 仅能看到其他玩家的公开发言（包含系统公开事件与玩家发言），并且该信息可用于推理与记录。

#### Scenario: Player sees another player's public speech
- **WHEN** 另一名玩家发布一条公开发言
- **THEN** 当前玩家在界面上可以看到该发言内容

### Requirement: Other players' role cards are hidden during the match
在非复盘阶段，系统 MUST 不向玩家展示其他玩家的身份牌信息（包含明示与任何可推断的“身份字段直出”形式）。

#### Scenario: Player cannot see another player's role card during the match
- **WHEN** 当前玩家查看任意其他玩家的信息区域
- **THEN** 系统不展示该玩家的身份牌内容

### Requirement: Inner thoughts are hidden during the match except for werewolf teammates
在非复盘阶段，系统 MUST 隐藏其他玩家的心声；唯一例外是当当前玩家为狼人阵营时，系统 MUST 允许其看到狼人队友的心声与发言。

#### Scenario: Good faction player cannot see anyone's inner thoughts
- **WHEN** 当前玩家为好人阵营且查看任意其他玩家信息
- **THEN** 系统不展示该玩家的心声内容

#### Scenario: Werewolf player can see werewolf teammates' inner thoughts
- **WHEN** 当前玩家为狼人阵营且查看狼人队友信息
- **THEN** 系统展示该队友的心声内容

### Requirement: Werewolf night chat is visible only to werewolves
狼人夜晚聊天内容 MUST 仅对狼人阵营玩家可见；非狼人阵营玩家在非复盘阶段 MUST 不可见该聊天内容与入口。

#### Scenario: Non-werewolf cannot view werewolf night chat
- **WHEN** 当前玩家为非狼人阵营并处于非复盘阶段
- **THEN** 系统不展示狼人夜聊的消息内容与相关入口

#### Scenario: Werewolf can view werewolf night chat
- **WHEN** 当前玩家为狼人阵营并进入夜晚狼人聊天可用阶段
- **THEN** 系统展示狼人夜聊消息内容

### Requirement: Replay phase reveals inner thoughts for review
在复盘阶段，系统 MUST 允许玩家查看心声等复盘信息（包括双方阵营），以支持复盘与学习。

#### Scenario: Player can view inner thoughts in replay
- **WHEN** 对局进入复盘阶段
- **THEN** 当前玩家可以查看其他玩家的心声内容

### Requirement: Werewolf teammates are visually marked for werewolf players
当当前玩家为狼人阵营时，系统 MUST 在玩家列表中对狼人队友进行明显且不影响布局的视觉标记，以便快速识别队友位置；非狼人阵营玩家 MUST 不可见该标记。

#### Scenario: Werewolf sees teammate markers
- **WHEN** 当前玩家为狼人阵营并查看玩家列表
- **THEN** 所有狼人队友头像/列表项显示队友标记

#### Scenario: Non-werewolf does not see teammate markers
- **WHEN** 当前玩家为非狼人阵营并查看玩家列表
- **THEN** 玩家列表不显示任何“狼人队友标记”
