# Reindeer 引擎详细知识库（AI 助手专用，比 HTML 教程更详尽）

本知识库用于给 Reindeer 本地 AI 助手提供比离线 HTML 教程更细致、更不容易混淆的参考。
当回答用户问题时，请以本知识库与检索到的教程片段为准，不要编造 API 或节点属性。

## 引擎身份与定位

Reindeer 是一个用 Python 编写、带图形化编辑器（基于 Qt / PySide6）、参考 Godot 设计风格的**可扩展 2D 游戏引擎**。
- 引擎核心（engine/ 目录）**零第三方依赖**，纯 Python 实现。
- 只有编辑器（editor/）需要 PySide6。
- 它不是 Godot、不是 Unity，是独立的自研引擎；设计风格“参考 Godot”不等于它就是 Godot。
- AI 助手自身的身份：Reindeer 2D 游戏引擎的官方中文助手。

## 编辑器界面详解（逐一辨认每个面板）

编辑器窗口由以下区域组成，位置固定，不要把它们混为一谈：

- **菜单栏（最上方）**：包含“文件、编辑、节点、视图、运行、帮助、测试”等菜单。重点入口：
  - 帮助 → 教程：打开离线 HTML 教程（web_doc/index.html）。
  - 帮助 → 脚本 API：打开完整脚本文档。
  - 测试 → AI 对话框（测试）：打开本 AI 助手。
  - 设置 → 工程设置 → 输入映射（Input Map）：定义输入动作与按键绑定。
- **主工具栏**：运行 / 停止 / 保存 / 撤销 / 重做等按钮；左侧还有“场景”下拉（切换已打开的场景）、新建节点、实例化节点等。
- **中央视口（Viewport）**：所见即所得的编辑画布，渲染当前场景；点击 ▶ Play 时实时预览运行效果。交互方式：
  - 左键拖拽：移动当前选中的节点。
  - 中键拖拽：平移视图。
  - 滚轮：缩放视图。
  - 空白处左键单击：取消选择。
- **左侧“场景树”（Scene 树 / SceneTreeDock）**：列出**当前打开场景**的节点层级（一个根节点 + 若干子节点）。在这里可以选中节点、右键添加子节点、复制、删除、拖拽调整父子关系。它只反映“内存中当前场景的节点结构”。
- **右侧“检查器”（Inspector / InspectorDock）**：显示当前选中节点的全部可编辑属性（由节点的 PROPERTIES 元数据自动生成控件），并可为节点**附加 .py 脚本文件**。
- **左下“文件系统”（FileSystem / FileSystemDock）**：浏览**磁盘上工程目录**里的文件与文件夹：.reindeer.tscn 场景文件、.py 脚本、图片贴图、音频等。右键可新建脚本 / 场景 / 文件夹；双击 .reindeer.tscn 会在视口与场景树中打开该场景。
- **底部“调试面板”（Debug / DebugPanel）**：实时显示 FPS、节点数、物理刚体数，以及脚本 print 输出的日志。
- **状态栏（最底部）**：显示就绪状态、节点数量、未保存标记（*）。

### 关键辨析：场景树（Scene 树）绝对不等于文件系统（FileSystem）

这两个面板最容易被弄混，但本质完全不同，**回答用户时务必区分清楚**：

- **场景树（左侧）**显示的是“当前已经打开、存在于内存里的一个场景的节点树”。你在场景树里看到的是**节点对象**（如 Player、Camera2D、Sprite2D），不是文件。
- **文件系统（左下）**显示的是“硬盘上的工程文件”。你在文件系统里看到的是**文件**（如 main.reindeer.tscn、player.py、icon.png），不是节点。
- 二者关系：在文件系统里**双击 .reindeer.tscn** → 引擎把该场景文件加载进来 → 它的节点才会出现在左侧场景树里。没有这一步，场景树里就没有对应节点。
- 因此，“在场景树里选中节点”和“在文件系统里打开场景文件”是两件事。**绝对不要把文件系统说成场景树，也不要把文件（.tscn / .py）说成节点。**

## 节点系统详解

- “一切皆节点（Node）”。一个**场景就是一棵节点树**：唯一根节点下挂子节点，子节点可继续嵌套。
- **父子关系**：子节点的 position / rotation / scale 是**相对父节点**的局部坐标。移动或旋转父节点，子节点跟着变换。
- **坐标**：每个 Node2D 有 position（局部坐标）和 get_global_position()（全局坐标，受所有祖先节点累积影响）。脚本里 set_position 改的是**局部**坐标。
- **绘制顺序（已可用，不是摆设）**：节点的 `z_index`（Node2D 上，-128~127）和 `CanvasLayer` 的 `layer` 属性**现在真实生效**。最终绘制顺序按 `(CanvasLayer.layer, z_index, 场景树顺序)` 排序：layer 大的整层（如 HUD）盖在 layer 小的世界层之上；同一层内 z_index 大的节点画在更上面；z_index 相同则后创建的（场景树里靠后的）画在上面。想让某个精灵永远在最前，就给它更大的 z_index（或放进更大的 CanvasLayer）。
- **生命周期回调**（脚本可定义）：_ready（进入场景时一次）、_process(delta 每渲染帧)、_physics_process(dt 每物理步)、_input(event)、_draw(renderer, cam)、_exit（节点移除时）。
- **场景文件格式**：.reindeer.tscn，本质是 JSON，记录节点树与属性，由 SceneLoader 读写。
- **节点注册**：所有节点（内置 / 插件 / 用户）通过 @register_node("类别") 注册进 NodeRegistry；编辑器“创建节点”对话框、场景加载器都只通过注册表发现节点，新增节点类型零侵入。

### 内置节点清单（按类别）

- Node（基础）：Node、CanvasLayer、Timer、Spawner
- Node2D（2D 物体基类，自带 position / rotation / scale / visible / **z_index**）：Node2D、Sprite2D、AnimatedSprite2D、Position2D、Path2D、PathFollow2D、ParallaxBackground、ParallaxObject、RemoteTransform2D、VisibilityNotifier2D
- Camera：Camera2D
- Physics：Area2D、CollisionShape2D、RigidBody2D、Joint2D
- UI：Button2D、ColorRect2D、Label、NinePatchRect、Node2DHelper、ProgressBar、TextureRect
- Visual：Light2D、Line2D、Particles2D、Polygon2D
- TileMap：TileMap
- PostFX：PostProcess
- Misc：Tween
- Audio：AudioStreamPlayer

（每个节点的详细属性与用法见“节点参考”下的单独 HTML 页面，知识库已一并索引。）

## 脚本系统详解

- 给任意节点**附加 .py 脚本**（在右侧检查器里指定脚本文件）。脚本是一个类，引擎在节点进入场景时实例化并注入 API。
- 在脚本里直接用 **self** 调用 API（引擎已注入便捷方法），也可用 self.api。常用 API：

  - 节点操作：get_node(path)、get_node_or_null(path)、get_parent()、get_tree()、get_children()、get_child(i)、get_child_count()、get_index()、get_path()、find_node(name)、has_node(path)、add_child(node)、remove_child(node)、reparent(node)、queue_free()、free()
  - 变换（Node2D）：get_position() / set_position(v)、get_global_position() / set_global_position(v)、get_rotation() / set_rotation(rad)、get_rotation_degrees() / set_rotation_degrees(d)、get_scale() / set_scale(v)、get_global_rotation() / set_global_rotation(rad)、get_global_scale() / set_global_scale(v)、set_visible(v)、is_visible()
  - 输入：is_action_pressed(a)、is_action_just_pressed(a)、is_action_just_released(a)、is_key_pressed(key)、is_mouse_button_pressed(b)、is_mouse_button_just_pressed(b)、get_mouse_position()、get_mouse_world_position()、get_viewport_size()
  - 信号：connect(signal_name, cb)、emit(signal_name, *args)
  - 资源：preload(path)（加载并缓存贴图 / 子场景）、load_scene(path)、instance(path)（载入并返回**新的**场景实例）
  - 计时：create_timer(interval, cb, oneshot=True)、remove_timer(handle)
  - 分组（标签化批量操作）：add_to_group(name)、is_in_group(name)、remove_from_group(name)、get_nodes_in_group(name)、call_group(name, 方法, *args)
  - 场景控制：set_pause(v)、is_paused()
  - 坐标转换（相对本节点）：local_to_global(local)、global_to_local(world)
  - 瞄准 / 几何：look_at(target)、distance_to(target)、angle_to(target)
  - 数学 / 工具：randf()、randi(a, b)、rand_range(a, b)、clamp(v, lo, hi)、lerp(a, b, t)、move_toward(cur, tgt, max_delta)、angle_difference(a, b)、is_instance_valid(obj)、get_global_mouse_position()、print(...)（输出到调试面板）、help()
  - 类型构造：self.Vector2(x, y)、self.Color(r, g, b, a)、self.Rect2(x, y, w, h)
  - 只读属性：self.delta（距上一帧的秒数）、self.time（引擎时间对象，含 fps / elapsed / delta）、self.node、self.engine、self.api

- **输入动作（action）**：在“设置 → 工程设置 → 输入映射”里定义按键绑定。内置动作始终可用：ui_left / ui_right / ui_up / ui_down / ui_accept / ui_cancel / ui_jump / ui_run。也可自定义（如 "fire"、"interact"）。
- **信号机制**：节点可定义 / 发出信号；用 connect("信号名", 回调) 连接。示例项目里 Enemy 闪烁就是通过 Area2D 的区域进入 / 离开信号实现的。
- 移动示例：

  def _ready(self):
      self.speed = 240.0

  def _process(self, delta):
      v = self.api.Vector2(0, 0)
      if self.is_action_pressed("ui_right"): v.x += 1
      if self.is_action_pressed("ui_left"):   v.x -= 1
      if self.is_action_pressed("ui_down"):   v.y += 1
      if self.is_action_pressed("ui_up"):     v.y -= 1
      self.node.position += v * self.speed * delta

## 物理系统详解

- 自研 2D 物理，由 PhysicsWorld 管理：重力、刚体、碰撞、关节、材质。
- **RigidBody2D**：动力学刚体，受重力与碰撞影响而运动。
- **CollisionShape2D**：碰撞形状，需挂在 RigidBody2D 或 Area2D 下，提供 circle / box / polygon 碰撞体。
- **Area2D**：区域，用于**检测重叠**而不产生物理反弹（传感），常用于收集物品、危险区域、触发事件。它只发信号、不做刚体碰撞响应。
- **重力**：PhysicsWorld 默认有重力，RigidBody2D 受其影响下落。
- **PhysicsMaterial**：弹性（restitution）/ 摩擦（friction）。
- **关节**：DistanceJoint / RevoluteJoint。
- **碰撞检测**：窄相位支持 圆-圆 / 圆-多边形 / 多边形-多边形（SAT + 裁剪），顺序冲量求解 + 位置修正。

## 插件系统详解

- 插件继承 Plugin，实现可选钩子：on_register_nodes / on_engine_ready / on_scene_loaded / on_frame / on_editor_ready / get_editor_panels。
- PluginManager.discover(path) 可扫描任意目录下的用户插件（addons）。
- 内置插件：TileMap（瓦片地图节点）、Light2D（光照）、PostProcess（后期处理）。
- 扩展方式：新增节点类型用 @register_node；新增插件放入工程 addons/ 目录，引擎启动时自动发现并注册。

## 相机 Camera2D 详解

- Camera2D 决定视口渲染的中心（世界 → 屏幕的投影）。
- 主要属性：
  - position：相机节点自身位置（若挂在玩家下则跟随玩家）。
  - limit_x / limit_y：世界边界限制，默认极大（= 不限制）；开启后相机中心不会离开该矩形世界范围。
  - smoothing（bool）：平滑跟随开关。
  - smoothing_speed（float，默认 5.0）：越大越跟手。
  - zoom：缩放。
- **让相机跟随玩家**两种方式：① 把 Camera2D 作为玩家节点的子节点（最省事，相机 position 自动跟随父节点）；② 单独放一个 Camera2D，每帧把它的 global_position 设为玩家位置。开启 smoothing 可平滑滞后跟随。
- world_to_screen / screen_to_world 都经过渲染中心计算，受 smoothing 与 limit 影响。

## 视差与立体纵深（ParallaxBackground + ParallaxObject）

引擎提供两个**真实可用**、相互配合的节点来营造深度感（近大远小、远近滚动速度不同）：

- **ParallaxBackground（Node2D）**：一个“铺满视口”的屏幕空间平铺背景，随相机滚动而产生视差。
  - `texture`：背景贴图（png/jpg）。
  - `parallax`（Vector2）：相机滚动量被应用到平铺的比例。0 = 完全钉在屏幕上（最远），1 = 和整个世界一起滚（最近）。典型值 0.2~0.6 表示远处的山/云。
  - `scroll`（Vector2）：额外的手动偏移，可在脚本里逐帧修改（如 `self.scroll = self.api.Vector2(t, 0)`）做流水、流云。
  - 用法：直接作为场景根的子节点放一个即可，它会自动填满视口；通常代表“最远层”。

- **ParallaxObject（Node2D，继承 Sprite2D）**：世界中的一个具体物体（树、陨石、星星），参与视差/透视。
  - `texture`：物体贴图（没有则画占位矩形），并继承 Sprite2D 的全部能力（flip、offset、modulate、精灵表）。
  - `depth`（0~1）：0 = 最远，1 = 最近。每帧按 `(相机渲染中心 - 相机起始渲染中心) * (1 - depth)` 偏移绘制位置——远物体几乎不动、近物体正常随世界移动，这就是视差。**注意：这里的“相机渲染中心”用的是相机 `_render_center()`（已含 smoothing 缓动与 limit 边界钳制），所以开启相机 smoothing 后，视差会跟随缓动后的镜头平滑滞后移动，而不是用未缓动的原始位置**——这正是之前“视差不跟缓动、仍用正常移动”问题的修复。
  - `perspective`（bool，默认开）：开启后绘制缩放取 `lerp(scale_far, scale_near, depth)`，即近大远小。
  - `scale_near` / `scale_far`：depth=1 / depth=0 时的绘制缩放，默认 1.5 / 0.5。
  - 用法：把 ParallaxObject 放在场景里当普通精灵用即可，无需挂在 ParallaxBackground 下；它自己读活动相机计算视差。要和 ParallaxBackground 配合：背景当最远层，多个 ParallaxObject 设不同 depth 当近/中层，就能得到明显的纵深。

组合示例：根下挂 `ParallaxBackground`(texture=云, parallax=0.2) + 若干 `ParallaxObject`(depth=0.3 远山、0.7 近树)，相机移动时远近滚动速度不一，纵深感立刻出现。

## 节点间配合（合作节点与组合用法）

引擎里有一批**专门用来“配合”其它节点**的节点 / 系统，把单个节点的能力串成完整玩法。优先用它们而不是手写重复逻辑：

- **RemoteTransform2D（Node2D）**：把本节点的**全局变换**实时推送给另一个节点（`remote_path` 指向目标），可分别用 `use_position` / `use_rotation` / `use_scale` 开关。典型配合：让影子 Sprite2D 跟随玩家、多个物体共享同一条移动轨迹、做镜像。目标必须是拥有 position/rotation/scale 的节点（Node2D 及其子类）。
- **Joint2D（Physics）**：把两个 RigidBody2D 用约束连起来协同运动。`joint_type = "spring"`（保持一段距离的 DistanceJoint，像弹簧/绳子）、`joint_type = "pin"`（钉在同一世界锚点的 RevoluteJoint，可相对旋转，像链条/摆锤）。用 `node_a_path` / `node_b_path` 指向两个刚体，引擎自动取它们的物理体建约束；`stiffness` / `damping` 实时可调。这是 RigidBody2D 之间的“合作”核心节点。
- **Spawner（Node）**：按 `interval` 实例化一个 .tscn 场景并作为自己的子节点；超过 `max_instances` 自动释放最旧实例（轻量对象池）。生成物可被自动加入 `group`，配合 `get_nodes_in_group` / `call_group` 批量控制（成批敌人、子弹、粒子化小物体）；`spawned` 信号带回刚生成的节点。可与 RigidBody2D、分组系统配合。
- **分组系统（SceneTree）**：用 `add_to_group(name)` 给节点打标签，再 `get_nodes_in_group(name)` / `call_group(name, 方法)` 批量操作——例如把所有敌人放进 "enemies" 组，一发 `call_group("enemies", "take_damage", 10)`。Area2D、Tween、Timer 等都能和分组组合出复杂逻辑。
- **Camera2D + ParallaxBackground + ParallaxObject**：见上一节，三层配合出纵深。
- **Area2D + RigidBody2D + 信号**：Area2D 检测重叠发信号，RigidBody2D 处理真实碰撞受力，两者通过分组/信号联动（如“碰到危险区 → 玩家扣血”）。

## 教程分阶段详细步骤（t1–t8）

- 第1阶段 第一个场景：新建 / 打开示例工程，认识视口与场景树，创建一个 Node2D 根节点，运行看空场景。
- 第2阶段 放置玩家精灵：在场景树下给根添加 Sprite2D（或选中 Player），在检查器设置 texture（贴图）为玩家图片；理解 Sprite2D 用于显示图片。
- 第3阶段 让相机跟随：给 Player 添加 Camera2D 子节点（或单独放 Camera2D 并每帧跟随），说明位置跟随与 smoothing。
- 第4阶段 脚本驱动移动：给 Player 附加 .py 脚本，用 _process + is_action_pressed("ui_right") 等 + Vector2 移动 position；解释输入映射与 delta 帧率无关。
- 第5阶段 收集物品：放置 Area2D + CollisionShape2D 作为可收集物；玩家用 Area2D 检测重叠，connect 区域信号或检测重叠来计数。
- 第6阶段 HUD 与计分：用 CanvasLayer + Label 显示分数（固定在屏幕上、不随相机移动），脚本更新 Label 文本。
- 第7阶段 危险与反馈：放危险区域（Area2D），进入时扣血 / 闪烁 / 重启，用信号与计时器实现。
- 第8阶段 综合实例 收集星星：综合运用精灵 / 相机 / 脚本 / 物理 / 区域 / 信号 / HUD，做成可玩的小游戏。

## 已实现的节点与功能清单（完善度，回答前务必核对）

下面是所有内置节点的**真实状态**。**只描述这里列出的能力，不要编造未列出的属性、方法或“配合方式”**。带 ✅ 表示功能完整可用，可放心向用户推荐。

| 节点 | 类别 | 真实能力 | 状态 |
|---|---|---|---|
| Node2D | Node2D | 位置/旋转/缩放/visible/**z_index**（绘制顺序已生效） | ✅ |
| Sprite2D | Node2D | 贴图/精灵表(hframes,vframes,frame)/居中/翻转/modulate；无贴图时画占位矩形 | ✅ |
| AnimatedSprite2D | Node2D | 按 fps 循环 frames 列表里的贴图 | ✅ |
| Label | UI | 文本/字号/颜色/对齐/描边 | ✅ |
| Button2D | UI | 矩形按钮+居中文字，鼠标松开且落在范围内时发 `pressed` 信号；支持 disabled | ✅ |
| ProgressBar | UI | 按 value/max_value 画背景+填充条 | ✅ |
| TextureRect | UI | 固定矩形内画贴图，支持 keep/tile/center | ✅ |
| NinePatchRect | UI | 九宫格缩放面板 | ✅ |
| ColorRect2D | Visual | 世界空间填充矩形 | ✅ |
| Polygon2D | Visual | 由 points 多边形填充（支持描边） | ✅ |
| Line2D | Visual | 从原点到 end 的直线 | ✅ |
| Light2D | Visual | 叠加径向光晕（additive） | ✅ |
| Particles2D | Visual | 粒子发射（速度/扩散/重力/生命周期/淡出） | ✅ |
| Camera2D | Camera | zoom/offset/current/smoothing/limit，world_to_screen/screen_to_world | ✅ |
| Area2D | Physics | 监测重叠，发 body_entered/exited、area_entered/exited（配合子 CollisionShape2D） | ✅ |
| CollisionShape2D | Physics | rect/circle/polygon 碰撞体，disabled 可关 | ✅ |
| RigidBody2D | Physics | dynamic/static/kinematic 刚体，重力/阻尼/弹性/摩擦，apply_impulse/set_linear_velocity 等 | ✅ |
| Path2D | Node2D | 折线点 + 绘制引导线 | ✅ |
| PathFollow2D | Node2D | 沿父 Path2D 移动（speed/loop/rotates） | ✅ |
| TileMap | TileMap | 网格彩色瓦片（cell_data + palette，视口裁剪） | ✅ |
| PostProcess | PostFX | 全屏暗角(vignette) | ✅ |
| CanvasLayer | Node | layer（-32~32）独立渲染层（常用于 HUD），绘制顺序已生效 | ✅ |
| Timer | Node | 计时器（脚本里也可用 create_timer 替代） | ✅ |
| Tween | Misc | 对目标节点属性缓动（duration/ease/repeat/autostart），发 tween_completed | ✅ |
| AudioStreamPlayer | Audio | 播放音效/音乐；**编辑器(Qt) 与独立打包(pygame) 都能发声**（自动回退） | ✅ |
| Position2D / Node2DHelper | Node2D | 空变换标记（出生点/枢轴） | ✅ |
| VisibilityNotifier2D | Node2D | 进出相机视口时发 screen_entered/exited | ✅ |
| ParallaxBackground | Node2D | 铺满视口的可视差平铺背景（parallax/scroll）；**已适配相机 smoothing 缓动** | ✅ |
| ParallaxObject | Node2D | 继承 Sprite2D，按 depth 做视差位移 + 透视缩放（perspective/scale_near/far）；**已适配相机 smoothing 缓动** | ✅ |
| RemoteTransform2D | Node2D | 把本节点全局变换实时推送给目标节点（use_position/rotation/scale 可分别开关）；用于影子跟随 / 镜像 / 轨迹共享 | ✅ |
| Spawner | Node | 按 interval 实例化场景并作为子节点；超过 max_instances 自动释放最旧实例（对象池）；生成物可自动加入 group，发 spawned 信号 | ✅ |
| Joint2D | Physics | 连接两个 RigidBody2D：joint_type=spring(距离/弹簧) 或 pin(锚点/旋转)；自动取物理体建约束，stiffness/damping 实时可调 | ✅ |

脚本 API 在“脚本系统详解”列出的方法之外，还新增：`look_at(target)`、`distance_to(target)`、`angle_to(target)`、`add_to_group(name)` / `is_in_group(name)` / `remove_from_group(name)` / `get_nodes_in_group(name)` / `call_group(name, 方法, *args)`、`instance(path)`（载入并返回**新的**场景实例）、`is_instance_valid(obj)`、`get_global_mouse_position()`、`set_pause(v)` / `is_paused()`、`local_to_global(local)` / `global_to_local(world)`、`move_toward(cur, tgt, max_delta)`、`angle_difference(a, b)`、`rand_range(a, b)`。节点可用 `self.get_tree().get_nodes_in_group(name)` / `self.get_tree().call_group(name, 方法)` 批量操作同组节点。

## 常见易错点 / 概念辨析（务必牢记，回答前先自检）

1. **场景树（左侧，节点树）≠ 文件系统（左下，磁盘文件）**。见上文“关键辨析”。这是最高频的错误，绝对不能把文件系统说成场景树，也不能把文件说成节点。
2. Node2D 的 position 是**相对父节点**的局部坐标；要世界坐标用 get_global_position()。
3. _process(delta) 是渲染帧（帧率相关），_physics_process(dt) 是物理步（更稳定）；移动物体通常用 delta 保证帧率无关。
4. 输入用“动作(action)”而非硬编码按键；ui_left 等内置动作始终可用；自定义动作在“设置 → 工程设置 → 输入映射”绑定。
5. 给节点加脚本是在**检查器**里指定 .py 文件，不是在文件系统里双击。
6. Camera2D 跟随：作为玩家子节点最省事；单独放时需每帧更新其 global_position。
7. Area2D 只检测重叠、不产生物理反弹；要真实碰撞 / 受力用 RigidBody2D + CollisionShape2D。
8. 不确定某个 API / 节点属性时，不要编造，建议用户打开“帮助 → 脚本 API”或对应节点的“节点参考”页面。
9. `z_index`（Node2D 上）和 `CanvasLayer.layer` 现在**真实生效**，决定谁盖在谁上面——不是摆设。想让某物永远置顶，就调大它的 z_index 或放进更大的 CanvasLayer。
10. `ParallaxBackground` 与 `ParallaxObject` 都是**真实可用**的节点（见“视差与立体纵深”一节），不要再声称它们“不够完善”或“需要额外插件”。ParallaxObject 直接当精灵用即可，无需挂在 ParallaxBackground 下。
11. `AudioStreamPlayer` 在编辑器(Qt) 与独立打包(pygame) 两种运行方式下**都能播放声音**，不要再说是摆设。
12. **只描述本知识库“已实现的节点与功能清单”里列出的节点与能力。** 若用户问到清单之外、你也不确定的功能，明确说“当前版本尚未实现 / 我无法确认”，**绝对不要凭空编造节点、属性或方法名**（例如不要臆造不存在的节点或参数）。
13. **视差已适配相机缓动**：ParallaxBackground / ParallaxObject 统一使用相机 `_render_center()`（含 smoothing 缓动与 limit 钳制）计算滚动，开启 Camera2D.smoothing 后视差会随缓动后的镜头平滑滞后移动；不要再告诉用户“视差不跟缓动 / 仍用原始移动”。
14. **RemoteTransform2D / Joint2D / Spawner 都是真实可用的协作节点**（见“节点间配合”一节），用于把单个节点串成完整玩法：变换推送、刚体约束、场景实例化对象池。需要时主动推荐，不要说它们不存在或“需要插件”。
