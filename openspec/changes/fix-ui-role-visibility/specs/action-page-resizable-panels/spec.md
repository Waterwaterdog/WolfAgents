## ADDED Requirements

### Requirement: Action page uses a vertical resizable split layout
“你的行动”页面 MUST 将“你的行动”区域与“游戏记录”区域以垂直方向上下分割展示，并且两区域共享同一页面可用高度，不得出现内容被另一区域遮挡的情况。

#### Scenario: Default layout renders both panels without overlap
- **WHEN** 用户打开“你的行动”页面
- **THEN** 页面同时展示“你的行动”和“游戏记录”两区域，且任何一方的内容不会覆盖另一方的可视区域

### Requirement: User can drag to resize panel heights
系统 MUST 提供可鼠标拖拽的分割条，使用户可以在不刷新页面的情况下调整“你的行动”与“游戏记录”两区域的高度分配。

#### Scenario: Dragging the splitter changes the panel heights
- **WHEN** 用户按住分割条并向上或向下拖动
- **THEN** “你的行动”与“游戏记录”两区域的高度按拖动方向实时变化

### Requirement: Panels enforce minimum usable height
系统 MUST 为上下两区域设置最小高度，以防止任意一块区域被拖拽到不可用（例如高度接近 0）。

#### Scenario: Dragging beyond minimum height clamps the result
- **WHEN** 用户将分割条拖拽到使任一面板低于其最小高度的位置
- **THEN** 系统将面板高度限制在最小高度，且拖拽仍可在允许范围内继续调整

### Requirement: Each panel scrolls independently
当“你的行动”或“游戏记录”内容超出其分配高度时，该区域 MUST 以自身滚动容器展示溢出内容，而不是扩展覆盖另一面板或导致页面整体不可控滚动。

#### Scenario: Long content scrolls inside its panel
- **WHEN** “你的行动”区域的文本内容超过其当前高度
- **THEN** 用户可以在“你的行动”区域内部滚动查看全部内容，且“游戏记录”区域的布局不发生覆盖或跳动

### Requirement: Resizing does not break content interaction
分割条拖拽调整高度 MUST 不影响两区域内部的交互（例如点击、选择、滚动），并且拖拽结束后系统 MUST 正常释放拖拽状态。

#### Scenario: After resizing, user can interact with both panels normally
- **WHEN** 用户完成一次拖拽调整并松开鼠标
- **THEN** 用户可以在两区域内正常滚动与点击交互，且光标/选择状态不会被持续锁定在拖拽模式
