# Reindeer 2D 游戏引擎

一个用 Python 编写、具备图形化编辑器、参考 Godot 设计风格的**可扩展 2D 游戏引擎**。
引擎核心**零第三方依赖**（纯 Python 实现），图形化编辑器基于 Qt（PySide6）。

---

## 快速开始

```bash
pip install -r requirements.txt      # 安装 PySide6（仅编辑器需要）
python run_editor.py                  # 启动编辑器，打开内置示例工程
```

编辑器启动后：

* **中央视口**：渲染场景，支持左键拖拽移动节点、中键平移、滚轮缩放。
* **左侧 Scene 树**：查看/选择/增删/拖拽节点（父子嵌套）。
* **右侧 Inspector**：按属性元数据自动生成编辑控件，可附加脚本文件。
* **左下 FileSystem**：浏览工程文件，双击 `.reindeer.tscn` 打开场景。
* **底部 Debug**：实时 FPS / 节点数 / 物理刚体数 + 脚本日志。
* **▶ Play / ■ Stop**：保存当前场景并在引擎中实时运行（含脚本与物理）。

打开内置示例工程后点击 **▶ Play**，用 **方向键 / WASD** 移动蓝色 Player，观察红色 Enemy 闪烁（信号机制）、绿色箱子受重力落下并落在地面上（物理系统），以及光照/后期/瓦片地图插件效果。

---

## 项目管理器（Project Manager）

启动编辑器时若**不传工程路径**，会先打开**项目管理器**：新建 / 导入 / 打开 / 删除工程，并作为入口进入编辑器；关闭编辑器后会自动回到管理器。

* **从资源包新建（二创 / Modding）**：点“从资源包新建”，选择一个 `.zip` 工程资源包，填写名称与位置，即可生成一份全新的可编辑工程——非常适合分享与二次创作。若资源包内没有 `project.reindeer`，引擎会自动补一个默认工程与起始场景。
* **导出为资源包**：选中工程后点“导出为资源包”，把整个工程（场景 / 脚本 / 贴图，自动排除 `__pycache__`、`.pyc`、构建产物等）打包成 `.zip` 方便分发。

## 内置 AI 助手（可选）

编辑器内置一个**本地运行**的 AI 对话（无需联网），用于解答引擎 / 节点 / 脚本 API 相关问题。它需要本地模型权重：把 `qwen.gguf`（或 `Qwen--Qwen3.5-0.8B/`）放到 `AI/` 目录即可。权重文件较大，已通过 `.gitignore` 排除，**请单独获取、不要提交**；未提供权重时 AI 菜单会提示缺模型，不影响其余功能。

## 架构（解耦 + 强可扩展性）

各系统之间通过**小而清晰的接口**通信，新增功能无需改动已有代码：

```
engine/
├── core/            # 引擎内核（无第三方依赖）
│   ├── math2d.py        Vector2 / Rect2 / Color
│   ├── signal.py        Signal / SignalEmitter（信号事件系统）
│   ├── input.py         InputManager（输入 / 动作映射）
│   ├── time.py          Time（帧时间 / FPS）
│   ├── resource.py      ResourceManager（资源缓存与加载）
│   ├── node.py          Node 基类 + 属性/序列化系统
│   ├── registry.py      NodeRegistry（节点类型注册表 ★）
│   ├── scene_tree.py    SceneTree（节点树 / 帧循环 / 生命周期）
│   ├── scene_format.py  SceneLoader（场景 JSON 存取）
│   └── engine.py        Engine（运行时顶层对象）
├── physics/         # 自研 2D 物理（刚体/碰撞/关节/材质）
│   ├── collider.py  Circle / Box / 多边形碰撞体
│   ├── collision.py 窄相位（圆-圆 / 圆-多边形 / 多边形-多边形 SAT+裁剪）
│   ├── body.py      RigidBody（动力学积分）
│   ├── joint.py     DistanceJoint / RevoluteJoint
│   ├── material.py  PhysicsMaterial（弹性/摩擦）
│   └── world.py     PhysicsWorld（重力/宽相位/顺序冲量求解/位置修正）
├── nodes/          # 内置节点（均通过 @register_node 自注册）
│   └── Node2D, Sprite2D, AnimatedSprite2D, ParallaxBackground, ParallaxObject,
│       RemoteTransform2D, Camera2D, CanvasLayer, Label, Button2D, TextureRect,
│       NinePatchRect, ProgressBar, Timer, Tween, Spawner, AudioStreamPlayer,
│       VisibilityNotifier2D, Path2D, PathFollow2D, Position2D, Light2D,
│       Line2D, Particles2D, Polygon2D, TileMap, PostProcess ...
├── rendering/      # 渲染抽象（默认 Qt/QPainter 实现）
│   └── __init__.py Renderer2D（draw_sprite / draw_light / draw_vignette ...）
├── scripting/      # 脚本系统
│   ├── api.py      ScriptAPI（丰富且文档完善的运行时 API）
│   └── script.py   脚本加载 / 实例注入 / 生命周期回调
└── plugins/        # 插件系统
    ├── plugin_base.py   Plugin 接口
    ├── plugin_manager.py PluginManager（发现/注册/钩子分发）
    ├── tilemap/         TileMap 节点（瓦片地图）
    ├── lighting/        Light2D 节点（光照）
    └── postprocess/     PostProcess 节点（后期处理）
editor/             # Qt 图形化编辑器
├── editor_window.py 主窗口（视口 + 各 Dock + 运行循环）
├── viewport.py     视口（渲染 / 输入 / 选择 / 平移缩放）
├── project.py      工程管理
├── docks/          SceneTree / Inspector / FileSystem / Debug
├── dialogs/        CreateNodeDialog（按类目搜索的节点选择器）
└── app.py          启动入口
example_project/    # 示例工程（演示脚本附加与运行）
├── scenes/main.reindeer.tscn
└── scripts/player.py, enemy.py
```

### 可扩展性的三个关键支点

1. **NodeRegistry（节点注册表）**：所有节点类型（内置 / 插件 / 用户）都通过
   `@register_node("类别")` 注册。编辑器“创建节点”对话框、场景加载器、脚本系统
   **只通过注册表发现节点**，因此新增节点类型零侵入。
2. **Plugin 接口**：插件只需继承 `Plugin` 并实现可选钩子
   （`on_register_nodes` / `on_engine_ready` / `on_scene_loaded` / `on_frame` /
   `on_editor_ready` / `get_editor_panels`）。`PluginManager.discover(path)`
   可扫描任意目录下的用户插件（addons）。
3. **属性元数据（PropertyDef）**：每个节点用声明式 `PROPERTIES` 描述可编辑字段，
   Inspector 据此**自动生成界面**，序列化/反序列化也据此完成——新增字段无需改 UI。

---

## 核心系统对照需求

| 需求 | 实现 |
| --- | --- |
| 节点系统 | `Node` 基类 + 父子树 + `SceneTree` 生命周期 + `.reindeer.tscn` 场景存取 |
| 物理系统 | 自研 `PhysicsWorld`：刚体、圆/盒/多边形碰撞、重力、冲量响应、摩擦/弹性材质、距离/销关节 |
| 脚本系统 | 为任意节点附加 `.py` 脚本，提供 `_ready/_process/_physics_process/_input/_draw/_exit` 生命周期，以及节点操作 / 输入 / 信号 / 资源访问 API |
| 编辑器界面 | 视口 + 场景树 + 检查器 + 文件系统 + 调试面板，支持拖拽、实时预览（Play） |
| 可扩展性 | 瓦片地图 / 光照 / 后期插件内置，并支持 `addons/` 目录导入插件 |

---

## 脚本 API（节选）

在脚本里你通常直接通过 `self` 调用（引擎已注入便捷方法）：

```python
def _ready(self):                       # 进入场景时调用一次
    self.speed = 240.0

def _process(self, delta):              # 每渲染帧
    if self.is_action_pressed("ui_right"):
        self.node.position += self.api.Vector2(self.speed * delta, 0)

def _physics_process(self, dt): ...     # 每物理步
def _input(self, event): ...            # 输入事件
def _draw(self, renderer, cam): ...     # 自定义绘制
def _exit(self): ...                    # 节点移除时
```

常用方法：`get_node(path)`、`get_parent()`、`get_tree()`、`add_child(node)`、
`is_action_pressed(a)`、`get_mouse_world_position()`、`connect(sig, cb)`、
`emit(sig, *args)`、`preload(path)`、`randf()`、`clamp()`、`print()`。
在编辑器菜单 **Help → Scripting API** 可查看完整文档。

---

## 扩展指南

### 新增一个节点类型
```python
from engine.core.node import PropertyDef, PT_FLOAT
from engine.core.registry import register_node
from engine.nodes.node2d import Node2D

@register_node("Custom")
class MyNode(Node2D):
    PROPERTIES = Node2D.PROPERTIES + [
        PropertyDef("power", PT_FLOAT, 1.0, group="Custom"),
    ]
    def _process(self, delta):
        ...
```

### 新增一个插件
```python
from engine.plugins.plugin_base import Plugin
from engine.core.registry import register_node

class MyPlugin(Plugin):
    name = "My Plugin"
    def on_register_nodes(self, registry):
        registry.register(MyNode, "Custom")
# 放入工程 addons/ 目录，引擎启动时会自动发现并注册
```

---

## 运行（无编辑器 / 命令行）

```python
from engine.core.engine import Engine
e = Engine(headless=True)
e.load_scene("example_project/scenes/main.reindeer.tscn")
e.run_scene("example_project/scenes/main.reindeer.tscn", frames=300)
```
