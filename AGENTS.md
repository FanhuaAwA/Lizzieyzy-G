# LizzieYzy GL：AI 重构、质量门与交接总文档

本文是 `F:/Lizzieyzy-GL/Lizzieyzy-G/` 唯一的 AI 项目总文档，适用于该重构源码目录下全部代码、文档、脚本和工作流。目标是让上下文有限的 AI 仍能持续、真实、可验证地完成长期重构。

最后更新：2026-07-14

---

## 0. AI 渐进阅读协议

不要每次默认把本文全部重复加载进工作上下文。先用 `rg -n "^## " AGENTS.md` 定位章节，然后按任务读取。

每次任务开始必须先读：

1. `§0 AI 渐进阅读协议`
2. `§1 当前真实状态`
3. `§2 不可协商规则`
4. `§12 未完成任务与交接台账`

再按任务补读：

| 当前任务 | 必读章节 |
| --- | --- |
| 项目理解、架构、模块拆分、技术选型 | §3、§4 |
| 配置、SGF/GIB、GTP、兼容迁移 | §4、§5 |
| 进程、网络、下载、更新、登录、WebView、IPC | §5 |
| UI、视觉、交互、性能、内存 | §6 |
| 任何产品代码、测试或构建变更 | §7、§8、§9 |
| GitHub Actions、三平台编译、制品、发布 | §10 |
| Git 分支、提交、推送、PR、CI 失败处理 | §2、§9、§10、§12 |
| 长期迁移阶段和下一步选择 | §11、§12 |

跨模块或大范围变更读取全部相关章节；只有任务确实横跨全部领域时才完整重读全文。随后只读取直接相关的代码、测试、配置、调用方和日志，不先遍历整个仓库。

标准工作闭环：确认台账任务 ID与完成条件 → 追踪真实数据流和全部调用方 → 实现最小可验收纵切 → 运行质量门 → review diff → 修复后复测 → 更新本文件台账 → 用证据交接。

项目内判断依据从高到低为：用户对当前任务的明确要求 → 本文不可协商规则和已批准决策 → 新版已验证代码/测试/制品行为 → 旧 Java 的可复现行为 → 旧代码注释、命名和猜测。发现冲突时记录证据并询问，不得静默选择方便实现的一方。旧版行为若明显导致安全问题或用户数据损坏，先保存兼容证据并请求裁决，不把漏洞原样迁移。

### 0.1 写代码前强制自检

未来 AI 不得凭“看起来知道”跳过以下问题。每项必须能用文件、代码、测试、命令或用户确认回答；答不出时先调查，仍无法确定再向用户询问，禁止先写代码碰运气。

- [ ] 本次对应哪个 `T-xxx`？若没有，先在 §12 建立任务。
- [ ] 用户可观察到的完成行为是什么？失败或取消时又是什么？
- [ ] 输入、处理、输出、持久化和外部依赖分别在哪里？
- [ ] 已用 `rg` 找到被修改符号的全部调用方、兄弟路径和现有测试了吗？
- [ ] 本次属于文档、小、中、大哪一级？是否触发 §5 安全升级？
- [ ] 哪条自动化测试会在实现出错时失败？没有测试时，本次必须补哪一个最小真实测试？
- [ ] 编译、测试、冒烟、功能实测分别执行什么命令和步骤？
- [ ] Git 工作树是否包含他人或用户未提交的修改？本次只会触碰哪些文件？
- [ ] 当前分支、远端 URL 和目标 GitHub 仓库是否已由用户确认？
- [ ] 完成后如何证明已提交、已推送且 GitHub Actions 通过？
- [ ] 本次功能等价矩阵的具体行、配置键或行为用例是什么？完成后会更新哪一项证据？

任一安全边界、远端归属、破坏性数据操作或完成标准不明确时，必须停止扩大修改范围。不得自行创造用户意图。

---

## 1. 当前真实状态

### 1.1 当前阶段

**阶段 1：基线建设进行中。**

原生 C#/.NET 10 + Avalonia 最小新壳及其测试已建立并通过本地质量门；旧版行为/配置基线正在 T-003 中建设，质量门脚本、GitHub Actions 和正式功能纵切仍未创建，因此不得把当前空棋盘壳称为可替代旧版的产品。

### 1.2 已确认事实

- 新版源码根目录：`F:/Lizzieyzy-GL/Lizzieyzy-G/`；Git 已连接公开远端 `https://github.com/FanhuaAwA/Lizzieyzy-G` 的 `main` 分支。仓库现有 `LizzieYzy.slnx`，包含 Core、Engine、Desktop 及三个对应 xUnit 测试项目。
- 旧 Java 行为基准：`F:/Lizzieyzy-GL/lizzieyzy-next-main/`，即 `../lizzieyzy-next-main/`；当前副本不含 `.git` 元数据。
- 旧项目使用 Maven；`pom.xml` 目标 Java 17，旧 GitHub CI 配置 JDK 21。
- 静态盘点：约 276 个主 Java 文件、179,215 行，约 145 个测试 Java 文件。
- 最大类包括约 18,146 行的 `LizzieFrame.java`、10,401 行的 `Menu.java`、5,618 行的 `Leelaz.java`。
- T-003 按“活跃字面量叶键 + 明确持久化 JSON 接收者”的当前静态口径检出 596 个配置键和 1,627 处引用，现有矩阵关联 50 个键；另有 37 个仅出现在 `Config.java` 注释中的历史候选键；其余 546 个字面量键、嵌套规范路径、计算键和逐用例语义归属仍未完成。
- T-003 按 `Menu.java` 中活跃的 `Menu.*`/`menu.*` 资源读取检出 383 个菜单资源键和 473 处引用，现有矩阵关联 52 个键；12 个活跃硬编码菜单字面量和两个显式 `setAccelerator`（`Shift+O`、仅 Windows 的 `Alt+O`）均已全部反向关联。十一个文件的十二个已纳入键源合计 140/140 个活跃 `VK_*` case、361/361 条路径；九个 pointer 源合计 32/32 个事件、76/76 条可达路径；全部反向关联 46 行矩阵并保留来源、修饰键、条件方法副作用、早退、空监听/空动作、执行语句、switch fall-through、数据依赖循环和原子 try/catch。代码库另有 9 个含键事件方法的文件和 21 个含鼠标事件方法的文件未纳入；其余 331 个菜单资源键也仍待盘点。
- AI 计算由外部 KataGo/Leela 进程承担；旧程序主要负责 GTP、规则/棋谱状态和 UI。
- 本机没有系统级 `mvn`，T-003 已在仓库外下载并校验 Apache Maven 3.9.16，在仓库外隔离副本以 Temurin 21.0.11 执行 `mvn -Dfmt.skip=true test`：1,161 项测试、0 failure、0 error、1 项按操作系统条件 skip；旧源码 576 个文件逐一比对无变化。
- 本机 `PATH` 当前先解析到 `C:/Program Files (x86)/dotnet/dotnet.exe`，该 x86 host 没有 SDK；项目命令必须显式使用 `C:/Program Files/dotnet/dotnet.exe` 的 x64 稳定 SDK。`global.json` 已固定 `10.0.103`、`latestPatch` 且禁止 preview；另有 `8.0.420` 和不得用于本项目的 `10.0.300-preview...`。
- T-002 使用官方 `Avalonia.Templates 12.1.0` 创建 Desktop，新壳和 headless 测试统一使用 Avalonia `12.1.0`，测试统一使用 xUnit v3 `3.2.2`。
- T-003 的机器可读矩阵位于 `migration/equivalence-matrix.json`，生成清单位于 `migration/legacy-inventory.json`；运行 `python scripts/generate_legacy_inventory.py` 生成，运行 `python scripts/generate_legacy_inventory.py --check` 验证来源指纹、证据、状态、配置引用、精确输入绑定和生成结果未漂移。

### 1.3 本文档已完成内容

- 固定 C#/.NET 10 + Avalonia 目标栈和最小模块边界。
- 定义安全边界、性能/视觉目标、质量门、真实冒烟、功能实测和大改 review。
- 定义 GitHub 三平台编译、测试、冒烟、发布和供应链规则。
- 建立未完成任务和 AI 交接台账；未创建假脚本、空 solution 或假工作流。

---

## 2. 不可协商规则

- 目标技术栈固定为 **C# / .NET 10 LTS + Avalonia UI**。改变技术栈必须由用户明确批准，并记录理由、替代方案和迁移影响。
- `../lizzieyzy-next-main/` 是旧版行为基准，默认只读；未经用户明确要求，不删除、批量格式化或在旧版内展开新架构重构。
- 按“可运行的纵向功能”渐进迁移，不按 Java 文件逐个机械翻译；旧 Java 只作行为对照，不作为新应用的运行时后端、发布保底或回退方案。
- 旧版全部有效功能、设置、数据格式和用户工作流都必须进入迁移矩阵并在新技术栈中真实实现。未经用户明确批准，不得静默删减、用近似功能替代或以“后续再做”宣称整体重构完成。
- 禁止假实现、空实现、未接线 UI、恒定成功、吞异常后成功、生产路径使用测试替身、没有行为断言的测试。
- 未完成或只完成一部分必须登记在 §12；不得写成“完成”“已支持”或用文案掩盖。
- 每次变更执行 §9 对应级别的质量门。中范围和大范围必须执行 Release 编译、测试、冒烟和受影响功能实测；纯小范围按 §9.2 的最小检查执行。没运行但按级别需要的项目明确写“未运行：原因”。
- GitHub 远端配置完成后，每一次中范围和大范围变更都必须形成边界清楚的本地 commit，推送到用户确认的 GitHub 分支，并等待必需 Actions checks 通过。纯小范围变更不强制单独提交或推送；累计修改一旦达到中范围，立即执行完整闭环，不得继续积攒。
- 对中范围和大范围变更，编译、测试、冒烟、功能实测、review、commit、push、CI 任一环节失败，该任务均未完成。允许保留明确标注的本地/WIP 状态，但不得提交到受保护分支或声称已经交付。
- 大范围变更必须在首次验证后重新从完整 diff 做独立 review，修复问题并重跑受影响质量门。
- 配置、棋谱、GTP、更新、下载和用户文件是兼容/数据安全边界，修改前先找全部读写路径与调用方。
- “世界顶级”“完美”只是方向，不是无证据结论。只有可复现质量门、实测数据、视觉/无障碍检查和 review 记录可以证明质量。
- 优先标准库、Avalonia 原生能力和仓库已有实现；不为推测中的未来需求引入微服务、数据库、插件平台、通用事件总线、单实现工厂或服务定位器。
- 用户指令和更高优先级安全规则优先。需要扩权、破坏性操作、未知程序执行、付费服务或外部发布时先获得授权。
- 产品任务不得顺手降低警告级别、删除测试、放宽质量门、改低变更分级或篡改完成条件。质量规则本身的调整必须是独立任务，说明影响，并由用户明确批准；规则冲突时临时采用更严格者。

AI 对用户和交接使用中文；代码标识符与公开 API 使用清晰英文。注释解释原因和约束，不复述代码。临时妥协必须带台账任务 ID。

---

## 3. 项目介绍、目标与非目标

LizzieYzy GL 是跨平台 AI 围棋桌面应用。它不是 KataGo 本体，主要职责包括：

- 围棋规则、落子、提子、历史树、分支、试下和棋谱编辑。
- SGF/GIB 等棋谱读取、保存、复制、恢复和兼容。
- 启动并管理 KataGo、Leela 等外部 GTP 引擎，解析持续分析结果。
- 候选点、变化图、胜率/目差曲线、热力图、问题手和形势判断。
- 快速全盘、批量、多引擎、AI 对局、时间控制与引擎参数。
- 野狐/腾讯/弈客相关棋谱、棋盘同步、远程算力和必要网页内容。
- 权重与运行时配置、GPU 检测、代理、更新、多语言、主题、窗口和无障碍。

长期目标：

- 所有关键功能和设置经过验证迁移，不丢用户数据。
- 前端现代、美观、信息层级清晰、可缩放、键盘与屏幕阅读器可用。
- GUI 空闲占用低，持续分析时 UI 流畅；KataGo 和 GUI 资源分开衡量。
- Windows、macOS、Linux 可重复编译、测试、打包、冒烟和发布。
- 规则、棋谱、配置、GTP 与 UI 解耦并可单独测试。
- 每个阶段都能独立运行并真实验收当前已迁移纵切；最终替代发布必须完成旧版全部有效功能与设置的原生重构，不依赖旧 Java 兜底。

非目标：重写 KataGo、建设云平台、支持所有历史魔改配置、为了“以后也许需要”建设复杂扩展系统。

### 3.1 功能等价矩阵是完整替代的唯一清单

T-003 必须在**本文 §12 的任务体系内**建立可检索的功能等价矩阵；为避免总文档膨胀，完整机器可读清单允许作为仓库测试数据生成，但本文必须记录清单路径、生成命令、摘要数量、未覆盖项和证据位置。禁止另建第二份 AI 规则文档。

矩阵最少逐行包含：稳定 ID、功能分类、旧版入口/菜单/快捷键、相关 Java 类与方法、相关配置键、输入与前置条件、成功行为、失败/取消行为、读写数据、外部依赖、目标 C# 模块、自动测试/语料、人工验收步骤、迁移状态和证据。当前静态口径的 596 个活跃字面量叶键必须能反向关联到至少一个读取/写入/迁移用例；不能只统计数量，后续发现的计算键或规范嵌套路径也必须纳入。

状态只允许：`未盘点`、`已盘点`、`实施中`、`已实现待验证`、`已验证`、`用户批准不迁移`。最后一项必须带用户批准记录；父分类只有全部子项为 `已验证` 或 `用户批准不迁移` 才能完成。截图、类名或按钮存在不等于功能通过，必须有可观察行为和验证证据。

---

## 4. 技术栈、目标架构与兼容契约

### 4.1 固定技术栈

- C#，.NET 10 LTS。
- Avalonia UI。
- 棋盘和图表优先使用 Avalonia 自定义控件/绘制；没有 profiler 证据时不加游戏引擎或独立渲染框架。
- 并发优先 `Task`、`async/await`、`CancellationToken`、`Channel<T>`。
- 进程使用 `ProcessStartInfo` 和标准输入输出。
- JSON/HTTP/WebSocket 优先 `System.Text.Json`、`HttpClient`、`ClientWebSocket`。
- 持久化先使用版本化 JSON、备份和原子替换；当前没有数据库需求。
- 发布先使用已验证的 self-contained 模式；Native AOT 在兼容和基准通过后再启用。

### 4.2 最小目录和模块

```text
AGENTS.md
.github/workflows/
src/Lizzie.Core/           # 规则、棋谱、历史、配置、领域模型
src/Lizzie.Engine/         # GTP、本地/远程引擎、进程生命周期
src/Lizzie.Desktop/        # Avalonia UI、组合根、平台入口
tests/Lizzie.Core.Tests/
tests/Lizzie.Engine.Tests/
tests/Lizzie.Desktop.Tests/
scripts/                   # 仅真实可运行的质量门、打包和冒烟脚本
```

旧 Java 基准位于源码根目录之外的 `../lizzieyzy-next-main/`，不得复制进新应用或作为运行时依赖。

边界：

- `Core` 不引用 Avalonia、不读全局窗口、不直接启动进程。
- `Engine` 依赖领域类型，不操作具体控件。
- `Desktop` 负责组合和展示，不复制规则、SGF 或 GTP 解析。
- 只有两个真实实现才抽接口；禁止新的全局可变单例和循环依赖。
- 状态流为：用户输入 → Desktop → Core 用例/状态 → Engine transport → 外部引擎；结果反向以类型化增量状态进入 UI。

依赖方向必须固定为：`Core` 无项目依赖；`Engine → Core`；`Desktop → Core + Engine`；测试项目只引用被测项目和确有必要的下层项目。任何反向引用、Desktop 类型渗入 Core/Engine 或循环依赖都必须在 build 前修正。

### 4.3 首次建仓与仓库基线

T-002 按以下顺序执行，不允许一次生成大量模板后不验证：

1. 运行 `Get-Command dotnet`、`dotnet --info` 和 `dotnet --list-sdks`，确认实际命中 x64 稳定 .NET 10。按 §1.2 当前机器应使用 `C:/Program Files/dotnet/dotnet.exe` 的稳定 `10.0.103`，可用完整路径或只调整当前 shell 的 PATH；未经授权不改系统级 PATH。用 `global.json` 固定真实稳定 SDK，并将 roll-forward 限制为 `latestPatch`；不得选 preview 或擅自降到 .NET 8/9。
2. 显式执行 `dotnet new sln --name LizzieYzy --format slnx`，只保留 `LizzieYzy.slnx`。从 .NET 10 起默认格式已是 SLNX，但仍写明 `--format slnx`，避免不同 SDK 产生两种 solution。
3. 用官方 Avalonia 模板创建 `Lizzie.Desktop`，用 SDK 模板创建两个 class library 和三个 xUnit 测试项目；全部目标框架为 `net10.0`。执行前用 `dotnet new list`/`dotnet new <模板> --help` 核对本机模板参数；缺模板时按 Avalonia 官方命令安装，并记录实际模板版本。
4. 把六个项目加入 solution，按 §4.2 添加项目引用；运行 `dotnet sln .\LizzieYzy.slnx list` 和各项目 reference 列表核对依赖方向。
5. 创建并提交 `Directory.Build.props`、`Directory.Packages.props`、`.editorconfig`、`.gitignore` 和 `global.json`。首次建仓或经批准更新依赖时，用一次非 locked restore **生成**各项目 `packages.lock.json`，逐项 review 后提交；禁止手写空 lock file。此后所有普通 restore 使用 `--locked-mode`。
6. 先完成能真实启动、关闭且没有假按钮的最小棋盘壳，再执行 locked restore、format、Release build、tests 和启动/退出实测；只有全部证据齐全才完成 T-002。

仓库基线要求：

- `Directory.Build.props` 统一启用 nullable、implicit usings、确定性构建、.NET analyzers、代码风格构建检查、warnings as errors 和 NuGet lock file；语言版本使用 .NET 10 默认稳定版，禁止 `preview`。
- `Directory.Packages.props` 集中固定**精确稳定版本**，禁止 `*`、浮动版本和未批准 preview；Avalonia 相关包保持同一兼容版本族。依赖变更必须更新并 review lock file。
- 测试框架统一为 xUnit；Avalonia 控件/布局/输入测试使用与 Avalonia 版本匹配的 `Avalonia.Headless.XUnit`。不得在 solution 中混用多套测试框架。
- `.editorconfig` 至少固定 UTF-8、LF、文件末尾换行、去尾随空格和 C# 风格；生成文件可有精确排除，不得全局关闭 analyzer。
- `.gitignore` 排除 `bin/`、`obj/`、`TestResults/`、`artifacts/`、coverage、日志、profiling、IDE 私有状态、本机用户数据、引擎、模型和秘密；不得忽略源码、fixture、`packages.lock.json` 或发布元数据。
- 默认只使用明确批准的 NuGet 源。新增私有源必须说明信任边界和凭据方式；凭据不得写入仓库。

工具命令会随 SDK/Avalonia 演进。执行 T-002 时必须以 [.NET 官方 solution 文档](https://learn.microsoft.com/dotnet/core/tools/dotnet-sln) 和 [Avalonia 官方入门文档](https://docs.avaloniaui.net/docs/get-started/) 复核模板命令，但不得借“文档更新”自行改变本文架构和质量要求。

### 4.4 C#、异步、资源与 Avalonia 实现规则

- 禁止在应用路径使用 `.Result`、`.Wait()` 或同步阻塞异步 I/O；`async void` 只允许 UI 事件处理器，且必须捕获、记录并向 UI 呈现失败。禁止无人持有、异常无人观察的 fire-and-forget 任务。
- 可取消的 I/O、引擎分析、下载和长任务从 UI 一直传递 `CancellationToken`；取消不是错误成功，必须停止后续写入并释放资源。`Channel`、队列和缓存必须有容量/淘汰策略。
- 流、进程、socket、timer、bitmap、订阅和取消源的所有权必须明确；使用 `using`/`await using` 或确定的 `Dispose`/`DisposeAsync`，关闭窗口和切换棋谱时验证无泄漏。
- UI 线程只做输入、轻量状态提交和绘制；文件、解析、网络、引擎读取不阻塞 UI。后台结果以不可变快照或有界增量传给 UI，只在真正更新控件时调度到 UI 线程。
- code-behind 只保留视图初始化和薄事件桥接；规则、解析、持久化、网络和引擎逻辑不得藏在 Window/UserControl。绑定优先编译绑定并声明 `x:DataType`；运行期 binding error 视为缺陷。
- 所有用户可见文本进入本地化资源，不在 ViewModel/控件中散落中文或英文；协议、配置和序列化使用不随系统区域变化的格式，展示层才按用户区域格式化。
- 异常只在能补充上下文、恢复或转换边界时捕获；禁止空 catch 和重复记录同一异常。日志使用结构化字段并按 §5 脱敏，用户错误不暴露堆栈和本机路径。
- 修复性能前先测量；禁止把所有 I/O 包进 `Task.Run`、用全局缓存掩盖问题、为单一实现增加无收益抽象，或复制同一状态到多个可写来源。
- 禁止重建旧版巨型 Window/Menu 类。新文件/类型持续膨胀、ViewModel 同时处理多个领域或方法包含多阶段流程时必须在 review 中说明拆分依据；行数只是风险信号，不得为达数字机械拆碎内聚逻辑。

### 4.5 配置兼容

- 第一版优先读取旧 `config.txt`、`persist` 和用户数据目录，不先发明新格式。
- 导入前备份；写入使用同目录临时文件、flush、原子替换，失败保留原文件。
- 当前静态口径的 596 个活跃字面量叶键必须有清单和迁移测试；未知键原样保留，保证完整审计并避免导入过程中丢数据。
- 密码不落盘；token/Cookie 按 §5 安全迁移。
- DNS、主机名或网络失败绝不能被当成“新机器”而删除配置。

### 4.6 棋谱与 GTP 兼容

- 固定 SGF/GIB 语料比较新旧节点数、主线、分支、落子、提子、手数、注释和关键属性。
- 保存后重读比较语义状态，不用字符串完全相同冒充正确性。
- 保存真实 GTP transcript，比较新旧候选点、胜率、目差、访问数和变化序列。
- 必须处理迟到响应、错误行、超长行、崩溃、取消、重启和退出；UI 不直接解析字符串或用 sleep 猜状态。

---

## 5. 安全边界

### 5.1 权限与执行

- 旧源码、棋谱、模型、引擎和下载文件均视为不可信输入。
- 未经授权，不运行来源未知的 EXE/DLL/脚本，不装驱动、不提权、不改系统代理/防火墙/注册表持久项。
- 未知程序动态测试先隔离，记录哈希、来源、参数、网络开关和产生文件。
- 不为测试关闭杀毒、证书校验、签名验证或系统安全功能。

### 5.2 子进程

- `ProcessStartInfo.UseShellExecute=false`，参数通过 `ArgumentList` 逐项传入；禁止拼接 shell 命令。
- 校验规范化绝对路径、允许目录、存在性和文件类型；支持中文、空格和长路径。
- 异步消费 stdout/stderr，设置行长、队列和取消上限，避免死锁和无限内存。
- 退出、切换、取消和异常时回收进程树；先优雅停止，超时后升级终止。
- 密码、token 不放入进程列表可见的命令行。

### 5.3 网络、认证与隐私

- 只连接功能必需端点；新增域名、遥测、上传或第三方服务需用户批准。
- HTTPS 验证证书与主机名；禁止“接受所有证书”。
- 密码不保存；记住登录使用系统安全存储，token 最小权限、可撤销、日志脱敏。目标平台无可靠安全存储时禁用“记住登录”，不得退化成明文文件。
- `HttpClient` 复用并设置超时、取消、响应上限；只对幂等操作做有上限退避重试。
- 诊断导出清除 Authorization、token、Cookie、隐私 ID、主目录和不必要的完整棋谱。
- 本地日志采用大小/数量上限和轮换策略，默认不记录完整棋谱、GTP 原文或响应正文；日志写失败不得拖垮主功能，也不得无限占满磁盘。
- 区分只读请求和外部写操作。发帖/聊天、上传棋谱、修改账号、启动远程任务、购买算力、产生费用或删除云端数据必须由用户在 UI 中明确触发并确认关键参数；自动测试只用沙箱/测试账号，禁止碰生产账号和产生真实费用。

### 5.4 下载与自动更新

- 仅 HTTPS；下载至少校验固定 SHA-256，正式更新验证签名清单。
- 校验在执行、解压、覆盖前；失败删除临时文件并保留当前已安装的新架构版本。
- 防 Zip Slip、绝对路径、符号链接逃逸、压缩炸弹和超大文件。
- staging → 完整验证 → 原子切换 → 安装事务失败恢复到上一个**新架构**安装；这只是更新安全，不是回退或调用旧 Java。绝不覆盖 `user-data`、配置、棋谱和用户模型。
- 下载进度来自真实字节，禁止定时器伪造；更新器不执行不可信 PR 或可写内容中的脚本。
- 自动下载的引擎/模型在哈希和来源校验完成前不得执行；用户手选的外部引擎必须显示规范化路径和风险，不得因“曾经选择过目录”自动运行后来被替换的文件。

### 5.5 文件与解析

- 外部路径规范化并验证仍在预期根目录；解析符号链接、junction/reparse point 后再次验证最终目标，删除、移动、覆盖前再检查一次。
- SGF/GIB/JSON/GTP 设置文件大小、节点数、深度、属性/行长、候选数和缓冲队列上限。
- 不信任扩展名、MIME、服务端字段和引擎输出；校验坐标、棋盘尺寸、数字和编码。
- 解析错误返回结构化上下文，不崩溃、不无限递归、不按攻击者输入巨量分配。

### 5.6 WebView、IPC 与供应链

- 主 UI 不依赖 WebView；仅必要网页视图使用 NativeWebView。
- 远程页面使用域名 allowlist/CSP，不暴露任意文件、进程、命令或通用原生桥。
- 本地 HTTP/WebSocket 仅绑定 loopback，使用随机会话 token、来源校验、大小限制；禁止默认 `0.0.0.0`。
- 新依赖必须说明标准库不足、许可证、维护、体积、AOT/跨平台和安全影响。
- NuGet 提交 lock file，CI locked restore；GitHub Actions 固定完整 commit SHA，默认只读权限。
- fork PR 不获取发布/签名 secrets；发布生成 SBOM、SHA-256 和构建来源信息。
- Git 远端 URL 必须逐字符匹配用户提供的仓库地址；地址未提供时不得猜测、创建相似仓库或推送到个人默认仓库。
- 不执行 `git reset --hard`、`git clean -fd`、强制 checkout 或强制 push，除非用户对准确分支和影响范围给出明确授权。
- 不 amend、rebase、覆盖他人已发布提交；发生远端分叉先 fetch、检查差异并说明，不用 `--force` 解决。
- commit 前只暂存本任务文件，逐行检查 staged diff 中是否包含 `.env`、私钥、token、Cookie、用户配置、日志、棋谱隐私或大型模型/二进制。

认证、更新、下载、子进程参数、IPC/WebView、用户文件迁移、解析上限或工作流权限变化，一律按大范围变更执行安全 review。

---

## 6. 世界级产品体验、视觉、可靠性与性能标准

“世界级”只能表示持续达到本节的可复现门槛，不能作为 AI 自评形容词。任何 UI 大改必须同时提供真实运行截图/录屏、任务完成时间或操作步骤、无障碍结果、性能数据和用户视觉确认；缺一项只能写“待验证”。

### 6.1 产品实用性与信息架构

- 围绕真实高频任务设计，而不是围绕代码模块堆页面：打开/恢复棋谱、浏览分支、配置并启动引擎、理解候选点与胜率/目差、试下/编辑、可靠保存与导出。
- 每个纵切先写用户、场景、入口、前置条件、主路径、失败/取消、恢复方式和完成信号；没有清楚任务流不得先画页面。
- 主棋盘始终是视觉中心；分析、历史、设置和日志按重要性渐进披露。新用户默认值安全可用，专业用户有快捷键、批量操作和可保存工作区，但高级选项不淹没主流程。
- 设置必须可搜索、分类、解释单位/范围，显示校验错误和未保存状态，并能恢复默认值；危险设置说明影响。不得要求用户理解 Java 字段名、GTP 原始文本或内部路径结构。
- 可逆编辑优先 Undo/Redo；不可逆、外部发布或付费动作才确认。取消、离线、引擎崩溃、权限不足、磁盘满等状态必须给出下一步，不把异常栈甩给用户。
- 首次启动无需账号即可完成本地棋谱和本地引擎流程；在线服务失败不应阻断本地功能。空、加载、部分结果、过期结果、错误、离线、取消和只读状态都要有明确设计。
- 大范围产品/UI 变更必须用至少 5 名目标用户或等价的结构化专家走查验证核心任务；记录成功率、阻塞点、误操作和修改结论。没有真实用户时标“未验证”，不得伪造研究结论。

### 6.2 视觉系统与界面完成度

- 在首个正式 UI 纵切前确定并由用户批准一套视觉方向、信息层级和 design token。token 至少覆盖语义颜色、字体/字重、间距、尺寸、圆角、边框、阴影、层级、状态、动效时长和图表色；XAML 中禁止散落重复魔法值。
- 建立可运行的组件展示页，覆盖按钮、输入、菜单、标签、对话框、通知、树、表、图表、引擎状态和棋盘标记的 normal/hover/pressed/focus/disabled/loading/error/selected 状态。展示页本身不能替代产品接线验收。
- 中文/日文/韩文与拉丁字体回退、字重、行高和数字对齐必须统一；胜率、目差、访问数等快速变化数字使用稳定布局，避免界面抖动。
- 图标采用同一套矢量语言、光学尺寸和线宽；禁止把 emoji、不同风格图标、任意渐变/阴影和无意义玻璃效果混在一起。装饰不得抢过棋盘、当前手和关键分析结论。
- 棋盘在分数 DPI 下仍要保证网格、星位、棋子、最后一手、提子、候选点和变化图清晰对齐；颜色、形状和文字共同编码，不能只靠红绿区别胜负或好坏。
- 窄窗口只允许有意的响应式重排/折叠，不能裁掉保存、退出分析等关键动作；常规窗口和 4K 大屏都不能出现巨大空洞、过密信息或失控行长。
- 视觉验收矩阵至少覆盖 Windows/macOS/Linux、浅色/深色/高对比度、100%/125%/150%/200% DPI、最小/常规/4K 窗口、中英文和超长文案。每次大改提供同场景截图；只有用户批准的基准才能更新，禁止用更新截图掩盖回归。
- 视觉精致不能牺牲可读性、性能和原生行为。动效必须解释状态变化、可中断并尊重系统“减少动态效果”；加载进度来自真实任务，禁止假进度。

### 6.3 无障碍与跨文化质量

- 以 [WCAG 2.2 AA](https://www.w3.org/TR/WCAG22/) 作为桌面 UI 最低可测基线：普通文本对比度至少 4.5:1、大文本和非文本关键图形至少 3:1；焦点不被遮挡，常用指针目标至少 24×24 逻辑像素或满足等价间距。
- 所有功能可仅用键盘完成，无键盘陷阱；Tab 顺序、快捷键冲突、焦点恢复、默认按钮和取消行为可预测。焦点样式在所有主题清晰可见。
- 使用 Avalonia `AutomationProperties` 和必要的自定义 automation peer，提供名称、角色、状态、帮助文本、标题/区域和动态状态播报；装饰元素不污染辅助树。
- Windows 用 Narrator/NVDA、macOS 用 VoiceOver、Linux 用 Orca/AT-SPI 至少各做发布前核心流程实测；平台能力缺失必须登记，不得仅凭属性存在宣称可用。
- 200% 缩放、系统大字体、长翻译、RTL 可预见布局和色觉缺陷模拟不能造成关键内容重叠、裁切或只能靠颜色理解。

### 6.4 高可用性、恢复与长稳标准

桌面软件的“高可用”定义为：本地核心功能不被可选服务拖垮，外部引擎/网络故障可隔离，应用异常退出后用户工作可恢复，长时间分析不退化。

- 目标 crash-free session ≥99.9%；数据只能来自 QA/用户自愿诊断，未经批准禁止遥测。样本不足时写“未测量”，不能写“达到”。
- 棋谱、设置和工作区使用原子保存与已验证备份；编辑中的未保存会话有受限、可清理的恢复副本。进程被强杀、系统重启、磁盘满和写权限丢失后，最近一次已确认保存绝不损坏，恢复副本状态向用户说明。
- 外部引擎崩溃、输出损坏、卡死或重启不得带崩 UI；状态明确变为不可用/可重试，停止使用过期分析结果并回收整个进程树。自动重试有上限且不重复付费或外部写操作。
- 网络、登录、WebView、远程算力和更新器相互隔离；单一在线服务不可用时，本地棋谱、编辑、保存和本地引擎仍可用。缓存损坏可重建，配置损坏优先恢复已验证备份并告知用户，不静默重置全部设置。
- 未处理异常必须进入顶层安全关闭/恢复路径并生成脱敏诊断；不得捕获后继续运行已知不一致状态。下次启动提供清楚恢复入口，而不是无限崩溃循环。
- 故障注入至少覆盖：恶意/截断 SGF、畸形 GTP、引擎强杀/卡死、断网、超时、HTTP 错误、磁盘满、只读目录、损坏配置、下载哈希错误和应用强杀。恢复行为必须有自动测试或可重复脚本。
- release candidate 至少完成一次 8 小时连续分析 soak、100 次棋谱打开/保存/关闭循环和 50 次引擎启动/取消/退出循环；不得出现未回收子进程、持续增长的线程/句柄/订阅或未处理异常。

### 6.5 首次完整替代发布前性能与资源预算

必须在 T-009 登记的固定参考机器、固定 Release 制品和固定语料测量，GUI 与 KataGo/模型分别记账：

- 无引擎时 GUI 空闲 60 秒 CPU p95 ≤0.5%，不得有无意义轮询、持续动画或定时重绘。
- GUI 空闲稳定后 RSS 目标 ≤120 MiB；平台运行时导致超出时必须有 heap/native profiler 证据、优化记录和用户批准，不能直接改高预算。
- 冷启动到主窗口可交互 p95 ≤2 秒；输入到可见反馈 p95 ≤100 ms。正常分析时帧时间 p95 ≤16.7 ms、p99 ≤33.3 ms，UI 线程无未解释的 ≥100 ms 停顿。
- 固定 10,000 节点 SGF 的解析与首屏 p95 目标 ≤500 ms，100,000 节点压力语料目标 ≤2 秒；耗时工作异步且可取消，历史树必须虚拟化，不能创建十万个可视控件。
- GTP 高频输出使用有界队列、合并和增量更新；每一行输出不能触发全窗口重绘。棋盘静态层缓存、脏区域重绘，render/layout 热路径不得持续装箱、LINQ 分配或重建全部集合。
- 核心 self-contained 桌面包（不含 KataGo、模型、用户数据和可选浏览器资源）目标 ≤80 MiB；每个新增依赖记录压缩后体积和启动/RSS 影响。
- 100 次打开/关闭大棋谱并强制稳定 GC 后，托管存活内存相对热身基线增长目标 ≤10 MiB，线程/句柄/子进程不得单调增长；8 小时 soak 热身后的 GUI RSS 趋势目标 ≤2 MiB/小时。

### 6.6 测量、回归拦截与专业验收

- 每组数据记录 commit、OS/架构、CPU/GPU/RAM、显示缩放、.NET/Avalonia/引擎版本、制品模式、语料哈希、运行次数、p50/p95/p99 和原始结果路径。只报一次最好成绩无效。
- 先预热，再至少 20 次短场景或足够时长的长场景；后台软件和电源模式保持一致。微基准只用于纯算法，真实启动、布局、渲染、I/O 和进程生命周期必须用最终制品测量。
- 热路径中范围/大范围变更与基线相比出现超过 5% 且超出噪声的退化，必须 profiler 定位、修复或由用户带证据批准；任何绝对预算失败都阻塞完整替代发布。
- 优先使用 `dotnet-counters`、`dotnet-trace`、GC/heap 工具和平台 profiler 获取证据；不得凭代码行数、Debug 运行或任务管理器瞬时截图下结论。
- UI 中范围变更做受影响页面视觉/键盘/性能检查；UI 大范围变更必须做全视觉矩阵、辅助技术实测和用户截图确认。性能/可靠性/视觉例外必须在 §12 单独登记负责人、影响和关闭条件，不能永久藏在备注。

迁移早期未覆盖的指标统一写“未测量”，不是“通过”。不得为数字删除安全、数据保护、正确性和无障碍；若目标间冲突，以测量和用户明确决策处理。

---

## 7. 完成定义与假实现禁令

出现任一情况不得报告完成：

- `NotImplementedException`、空方法/事件、固定成功返回。
- 按钮/菜单/设置/进度条未接真实用例。
- 捕获异常后忽略、默认成功或伪造错误恢复。
- 生产代码调用 fake/mock/stub；测试替身只允许在测试边界。
- `Assert.True(true)`、无行为断言、跳过失败测试来过 CI。
- 用“进程存活几秒”代替语义冒烟，用固定 JSON/截图冒充真实结果。
- 没有台账 ID 的 TODO/FIXME/临时兼容层。

功能完成必须同时满足：入口、领域逻辑、真实依赖和错误路径接通；正常/边界/取消失败有自动测试或可重复实测；资源释放和数据兼容已验证；相关 §6 实用性、视觉、可靠性、性能预算已测或明确登记未测；UI 文案、键盘、焦点、缩放和无障碍已检查；对应质量门通过并有证据；没有未登记半成品。

需要分期时，交付可工作的部分，并在 §12 写清可用范围、不可用范围、用户影响、下一步和验证方法。半成品可存在，但不能隐瞒。

---

## 8. 变更分级

按风险最高项定级，文件数仅辅助：

| 级别 | 定义 |
| --- | --- |
| 文档级 | 只改本文/注释，产品、配置、脚本、依赖、工作流均未变 |
| 小范围 | 单一局部行为，通常 ≤3 个产品文件，不改公共契约、持久化或协议 |
| 中范围 | 一个完整纵切或子系统，涉及多层/集成点，但边界清楚且变更可安全撤销 |
| 大范围 | 跨子系统、架构/API、配置迁移、协议、安全边界、依赖、打包发布或大批机械变化 |

认证、更新、下载、用户数据、命令执行、WebView/IPC、工作流权限始终至少按大范围处理。

---

## 9. 质量门、冒烟、功能实测与大改 Review

### 9.1 .NET 通用门

solution 存在后，基础命令固定为：

```powershell
dotnet --info
dotnet restore .\LizzieYzy.slnx --locked-mode
dotnet format .\LizzieYzy.slnx --verify-no-changes --no-restore
dotnet build .\LizzieYzy.slnx -c Release --no-restore /warnaserror
dotnet test .\LizzieYzy.slnx -c Release --no-build --logger "trx;LogFileName=tests.trx"
```

- 当前 solution 不存在，这些门是“未实现”，不得伪造成功。
- 启用 nullable、.NET analyzers、确定性构建、warnings as errors。
- NuGet lock file 提交，CI `--locked-mode`；依赖升级单独 review 后重新锁定。
- T-005 完成后，跨平台统一入口为 `pwsh ./scripts/quality.ps1 -Level Medium` 或 `-Level Large`。脚本必须打印实际子命令、顺序执行本节门、首个失败即非零退出，并生成证据摘要；不得修改源码、自动跳过、自动提交或推送。脚本损坏时仍可用上面的显式命令复核，禁止空壳 gate 脚本。

#### 9.1.1 测试分层与确定性

- `Core` 单元测试不访问网络、真实用户目录、进程或 UI，覆盖规则、历史树、SGF/GIB、配置迁移的正常/边界/错误/回滚行为。
- `Engine` 协议测试使用确定性测试 GTP 子进程覆盖分块输出、迟到响应、错误、取消、背压、崩溃和退出；它只能存在于测试边界。真实 KataGo 集成测试单独标记，固定版本、模型和 SHA-256。
- ViewModel 用普通单元测试；涉及 Avalonia 控件、布局、绑定和输入时用 `Avalonia.Headless.XUnit`；涉及真实渲染、DPI、文件对话框、剪贴板、窗口管理、GPU 或辅助技术时必须在目标 OS 运行真实窗口测试。headless 不能替代桌面实测。
- 集成测试只使用仓库 fixture 和每测试独立临时目录，禁止读写真实用户配置。fixture 必须无隐私、固定编码/时区/culture/随机种子并记录来源与哈希。
- 禁止用无条件 sleep 等待异步状态；使用事件、可控时钟或带诊断的有限 timeout。失败测试不得靠重跑到成功；flaky 测试先标任务、保留失败证据并修根因，不能长期 quarantine。
- 每个 bug 修复先增加能稳定复现的回归测试，再修实现。解析器、配置和 GTP 等不可信输入边界维护恶意/截断语料并做有上限 fuzz/property 测试，验证不会崩溃、挂死或无限分配。
- 关键规则、SGF、配置迁移和 GTP 状态机在完整替代发布前分支覆盖率目标 ≥90%，并覆盖所有已知失败/取消/恢复分支；覆盖率只是缺口信号，不能用无行为断言刷数字。
- 测试本身必须经过故意引入缺陷或等价 mutation 抽查，证明关键断言会失败；CI smoke/安全门也要验证至少一个预期失败样本确实被拦截。

### 9.2 各级必过门

| 检查 | 文档 | 小范围 | 中范围 | 大范围 |
| --- | :---: | :---: | :---: | :---: |
| diff/状态与意外文件 | 必须 | 必须 | 必须 | 必须 |
| 文档结构/一致性 | 必须 | 相关时 | 相关时 | 必须 |
| format + Release build + 全部单元测试 | 不适用 | 不强制 | 必须 | 必须 |
| 受影响功能针对性测试 | 不适用 | 有现成快速检查时建议 | 必须 | 必须 |
| 启动/退出冒烟 | 不适用 | 不强制 | 必须 | 必须 |
| 真实功能实测 | 不适用 | 不强制 | 必须 | 必须 |
| 安装/便携制品冒烟 | 不适用 | 不强制 | 桌面相关时 | 必须 |
| 性能数据 | 不适用 | 不强制 | 关键样本 | 完整基准对比 |
| DPI/键盘/视觉/无障碍 | 不适用 | 不强制 | UI 相关时 | 必须 |
| 故障注入与数据恢复 | 不适用 | 不强制 | 受影响边界 | 必须 |
| 长稳/泄漏测试 | 不适用 | 不强制 | 生命周期/性能相关时 | release candidate 或相关大改必须 |
| 安全 review | 不适用 | 安全相关则升级 | 安全相关则升级 | 必须 |
| 全 diff review，修复后复测 | 简要 | 简要 | 必须 | 强制 |
| 本地 commit + 推送 GitHub | 不强制 | 不强制 | 必须 | 必须 |
| GitHub 必需 Actions checks | 不强制 | 不强制 | 必须 | 全部必须通过 |

文档级可跳过产品编译，但交接必须写“不适用：仅文档”。

纯小范围变更只强制检查 diff、意外文件和明显错误，不要求完整编译/全量测试/冒烟，也不要求单独 commit/push。若修改公共契约、配置、协议、依赖、构建、工作流、安全边界，或多个小改累计形成完整功能/多个文件联动，就不再属于小范围，必须升级为中范围并执行完整质量门和 GitHub 交付。

### 9.3 冒烟最低语义

冒烟不能只看窗口或进程：

1. 从实际发布目录启动，验证用户目录可写和配置加载。
2. 打开固定 SGF，核对棋盘尺寸、主线手数、分支和当前手。
3. 启动固定版本真实 KataGo，发送生产 GTP 命令，得到可解析候选点/胜率。
4. UI 显示结果、切换手数且保持响应。
5. 保存到临时位置并重读，语义状态一致。
6. 正常退出，引擎进程树结束，配置未损坏，日志无未处理异常和秘密。

每 PR 可以用确定性测试 GTP 进程覆盖时序/错误，但不能代替合并前和发布前真实 KataGo 冒烟。若实现 `--smoke`，必须走生产组合根、解析和持久化，只允许自动输入，不允许专用永远成功分支。

### 9.4 受影响功能实测

- 规则/SGF：真实语料，核对节点、分支、提子、注释和 round-trip。
- GTP/引擎：transcript + 真实 KataGo，测试启动、分析、取消、崩溃和退出。
- 设置：旧配置副本迁移，验证备份、已知/未知键、失败回滚。
- 下载/更新：受控端点，验证哈希失败、取消、空间不足、回滚和路径穿越拒绝。
- UI：实际启动，检查目标 DPI、窗口变化、键盘、焦点、无障碍名称、空/加载/错误态。
- 在线功能：授权范围内真实协议实测；服务不可用时写“未验证”，mock 不能证明完整完成。

### 9.5 大范围变更强制 review

首次验证后重新从完整 diff 检查并回答：

- 是否符合需求并覆盖兄弟调用方、失败、取消和回滚？
- 是否引入全局状态、循环依赖、重复逻辑或过度抽象？
- async、线程切换、Channel/事件是否竞态、死锁、泄漏或无界排队？
- 进程、流、socket、timer、bitmap、订阅是否确定释放？
- 高频路径是否重复分配、全量重绘或阻塞 UI？
- 输入、凭据、日志、路径、下载、工作流权限是否安全？
- 配置/棋谱是否完整兼容，迁移写入失败时是否可恢复原始用户数据？
- UI 是否覆盖加载、空、错误、禁用、焦点、DPI、无障碍？
- 是否有死代码、临时代码、重复依赖和可删除实现？

发现问题必须修复并复测。无法本次处理的项进入 §12，状态不得为完成。

### 9.6 验证证据

每次交接记录 OS/架构/.NET/引擎版本、完整命令、退出码、通过/失败/跳过数、制品路径、冒烟语义、性能场景与数据、未验证项，以及 Git 分支、完整 commit SHA、远端 URL、push 结果、PR/Actions run URL。没有证据就写“尚未验证”，禁止“应该没问题”。

### 9.7 失败时必须采取的动作

| 失败情况 | 必须动作 | 禁止动作 |
| --- | --- | --- |
| 工作树有无关修改 | 不暂存；确认所有者和重叠范围，无法隔离则停止并询问 | 覆盖、删除、顺手格式化或一起提交 |
| restore/build/format 失败 | 定位并修复根因，重新从失败门开始运行 | 跳过、降低 warning、改 Debug 冒充 Release |
| 自动测试失败 | 复现根因并修复代码或正确测试，重跑全部相关测试 | 删除断言、增加盲目 sleep、skip 测试 |
| 冒烟/功能实测失败 | 保留日志和输入，任务标未完成，修复后完整重测 | 仅凭单元测试宣称完成 |
| 环境缺失导致无法实测 | 在 §12 写具体缺失物并报告阻塞 | 写“理论可用”或伪造成功输出 |
| commit 前发现秘密/用户数据 | 取消暂存并移除，必要时轮换泄露凭据 | 先提交再删除；秘密会留在历史中 |
| push 失败 | 保留本地 commit，记录错误和远端，任务仍未交付 | 声称已上传或改推未知仓库 |
| Actions 失败 | 读取真实日志，提交新的修复 commit，再等待 checks | force-push 隐藏失败、重跑到偶然成功却不修根因 |
| 远端有新提交/分叉 | `git fetch` 后 review 差异，选择安全 merge/rebase 方案并说明 | `--force`、删除远端提交、盲目覆盖 |

---

## 10. Git/GitHub 提交、三平台编译、冒烟与发布

当前工作流尚未实现。

### 10.1 `ci.yml`

触发 `pull_request`、默认分支 push、`workflow_dispatch`；默认 `permissions: contents: read`，同分支取消过期运行。

必须：

1. checkout 不持久化凭据；action 固定完整 commit SHA并注释上游版本。
2. 按 `global.json` 安装固定 `10.0.xxx` 稳定 SDK，校验没有使用 preview，并打印 `dotnet --info`。
3. 一个 job 验证格式。
4. Windows/macOS/Linux 原生 runner matrix 分别 locked restore、Release `/warnaserror` build、全部 unit/integration/headless test。
5. 运行规则、配置、GTP 固定语料集成测试、覆盖率缺口检查和预期失败样本；不得把缺少真实依赖误报成通过。
6. 失败时上传 TRX、覆盖率摘要和脱敏日志，不上传 secrets、用户目录或完整隐私数据。

建议必需检查名：`format`、`build-test (windows)`、`build-test (linux)`、`build-test (macos)`、`smoke-fast (windows)`。

### 10.2 `smoke.yml`

- 每 PR 快速层：实际打包，生产路径 SGF + 确定性 GTP，验证语义、保存、退出。
- 默认分支/定时/release candidate 真实层：固定版本和 SHA-256 的真实 KataGo；Windows 强制，发布前 macOS/Linux 强制。
- 无法获得真实引擎时真实层失败或阻塞发布，禁止自动降级 fake 后通过。
- GitHub runner 无法可靠 GUI 交互时使用生产 `--smoke` 自动入口，同时保留真实桌面 UI 实测。

### 10.3 `release.yml`

仅受保护 tag 或手动明确版本触发：

1. 验证版本、来源和全部必需 checks。
2. 三平台原生 runner 干净 restore/build/test/publish/package。
3. 对最终安装/便携制品执行真实 SGF + KataGo + 保存 + 退出冒烟。
4. 生成 SHA-256、SBOM、依赖/许可证和构建元数据。
5. 使用受保护 environment 和人工批准；有 secrets 才签名/公证，缺失时不得声称已签名。
6. 发布说明列出已验证平台、迁移风险和已知未完成项。

发布候选还必须引用 §6.4 长稳/故障恢复报告和 §6.2 视觉验收矩阵；报告缺失、预算失败或用户尚未确认重大视觉变更时，不得发布“完整替代”版本。

### 10.4 `security.yml`

- 在 PR 依赖/工作流变化、默认分支 push、每周定时和手动触发时运行；默认只读，只有 CodeQL 上传结果的 job 获得最小 `security-events: write`。
- 对 C# 运行 CodeQL 或等价的真实静态安全分析，对全部直接/传递 NuGet 依赖运行 audit，对许可证、已知高危漏洞和秘密模式做检查；high/critical 漏洞或真实秘密阻塞合并。
- 低/中风险必须有台账任务、影响判断和关闭日期，不能通过全局 suppress 消失。误报 suppress 必须精确到规则/路径并记录证据。
- 工作流权限、action SHA、fork 行为和 artifact 内容必须有测试；安全工作流只有真实发现样本能导致失败、清洁样本能通过后才算完成。

### 10.5 可复现和供应链

- 只缓存 NuGet 下载，不缓存 `bin/obj` 冒充构建结果。
- cache key 包含 OS、SDK 和 lock file 哈希，cache miss 仍必须可构建。
- 不在 CI 自动升级依赖；依赖升级单独 PR。
- fork PR 不读取 secrets；禁止用 `pull_request_target` checkout 不可信代码后执行。
- job 最小权限，发布 job 才单独 `contents: write`；签名密钥只给签名步骤。
- 工作流只有在真实 Actions 成功运行、故意失败能正确拦截、三平台产物/日志正确、run URL 记入 §12 后才算完成。

### 10.6 每次变更的 Git 提交与推送标准流程

以下流程在用户提供 GitHub 地址并完成 T-010 后，对每次中范围和大范围变更强制执行。纯小范围变更不强制单独提交；累计达到中范围时，必须把累计 diff 作为一个完整中范围变更执行本流程。命令中的 `<...>` 必须替换为本次真实值，不得原样执行。

#### A. 修改前确认仓库和分支

```powershell
git status --short --branch
git remote -v
git branch --show-current
git fetch --prune origin
```

逐项确认：

1. 当前目录是 `F:/Lizzieyzy-GL/Lizzieyzy-G/` 对应仓库。
2. `origin` 与用户提供的 URL 完全一致；不一致立即停止。
3. 记录已有 dirty 文件，区分用户修改与本任务修改。
4. 默认不直接在 `main`/`master` 开发；从最新受保护分支创建 `task/T-xxx-short-name`。用户指定分支时遵循用户要求。
5. fetch 后如远端历史变化，先理解差异，不盲目 rebase/merge。

#### B. 修改完成但尚未提交

依次完成 §9 的 format、Release build、全部测试、针对性测试、冒烟、功能实测和 diff review。任何必需门失败都不能进入提交步骤。

```powershell
git status --short
git diff --check
git diff --stat
git diff
```

确认没有生成物、缓存、秘密、用户数据、无关格式化和旧 Java 意外修改。

#### C. 精确暂存与提交

```powershell
git add -- <本任务文件1> <本任务文件2>
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "<type>(<scope>): <真实变更摘要> [T-xxx]"
```

- 禁止无检查的 `git add .`、`git add -A`。
- 一个 commit 只表达一个可独立 review、已验证的逻辑变化。
- 常用 `type`：`feat`、`fix`、`refactor`、`test`、`build`、`ci`、`docs`、`perf`。
- commit message 不写 `update`、`misc`、`work`；必须说明真实行为。
- 提交后运行 `git status --short --branch` 和 `git show --stat --oneline HEAD`，确认无遗漏或混入文件。

#### D. 推送与 GitHub 验证

```powershell
git push -u origin HEAD
git rev-parse HEAD
git ls-remote --heads origin (git branch --show-current)
```

本地 `HEAD` 与远端分支 SHA 必须一致。随后创建或更新 PR，并等待 branch protection 要求的全部 checks 通过；有 GitHub CLI 时可使用 `gh pr checks --watch`，否则读取 GitHub Actions 页面。记录 PR URL、run URL 和最终结论。

push 成功但 CI 未通过时，任务状态仍是“进行中”。修复使用新的 commit，保留可审计历史；未经用户明确授权不 amend 已推送提交、不 force-push。

#### E. 远端尚未配置时

本项目已于 2026-07-13 完成 T-010；本节仅作为未来远端缺失或失效时的处理规则。可以完成文档或本地实现与验证，但无法满足“提交到 GitHub”的交付条件。不得自行初始化到未知远端；在 §12 标记阻塞并等待用户提供仓库 URL、默认分支和授权方式。

---

## 11. 渐进迁移阶段

每阶段通过 §9 才能标完成：

1. **基线**：功能矩阵、当前 596 个活跃字面量配置叶键及后续发现项、SGF/GIB、GTP transcript、旧版截图和 GUI/引擎分离性能。
2. **新壳**：Avalonia 启动、主题、语言、窗口、设置只读导入；不放假按钮。
3. **棋谱查看器**：规则、历史树、SGF/GIB、主棋盘、分支导航和兼容保存。
4. **本地分析**：真实 KataGo、GTP、候选点、变化、胜率/目差和优雅退出。
5. **编辑与高级分析**：试下、编辑、批量/全盘、多引擎、AI 对局、时间和参数。
6. **在线与平台能力**：站点棋谱、同步、远程算力、代理、下载、更新和 WebView。
7. **完整替代发布**：跨平台包、全部功能/设置迁移验收、数据失败恢复、无障碍、视觉回归、性能门和真实用户验证。

旧 Java 只允许作为测试预期、截图、配置和协议行为的对照，不得被新 UI 调用、随新应用打包或作为生产 fallback。阶段性版本可以只开放已完成纵切，但“完整替代”必须由 C#/.NET/Avalonia 原生覆盖迁移矩阵中的全部功能和设置。

---

## 12. 未完成任务、半成品与 AI 交接台账

### 12.1 当前任务表

| ID | 状态 | 任务 | 完成条件/下一步 |
| --- | --- | --- | --- |
| T-001 | 完成 | 确定新版源码目录 | 用户已确认 `F:/Lizzieyzy-GL/Lizzieyzy-G/` 为重构后源码根目录 |
| T-002 | 完成 | 创建最小 .NET 10 + Avalonia SLNX solution | SDK/依赖/锁文件、3 个产品项目和对应测试、真实空棋盘启动退出、format、Release build、5 项 tests 和依赖审计均通过；实现提交 `c17873dde901b77637e770c241dbdc3e3037218a` 已推送，draft PR `#1` 为 OPEN/CLEAN；Actions 尚未建立并由 T-006 跟踪 |
| T-003 | 进行中 | 建立旧版行为基线和功能等价矩阵 | 已校验便携 Maven 并在隔离副本跑通旧版 1,161 项测试；已生成 576 文件来源指纹、596 活跃配置叶键/1,627 引用、37 注释候选键、383 菜单资源键/473 活跃引用、12 个硬编码菜单字面量，以及十二个文件的十三个键盘来源共 141 个 case/362 条路径、十个 pointer 来源共 33 个事件/79 条路径，并建立 46 个 `已盘点` 用例；当前关联 50 配置键、53 菜单资源键、全部菜单字面量/accelerator 和已纳入输入源的全部 case/事件/路径；提交 `2ff509b71dbd999beb9ee61d29342a42cecdc59b` 扩充 `ONLINE-FOX-001`，补入 FoxKifuDownload 的三个入口、Enter、表格三条点击路径、共享代理/贴目/自动快速分析配置、联网/SGF/生命周期与失败边界，位于 draft PR `#2`；下一步盘点剩余文件中最小且同时含键盘和鼠标监听器的 `BrowserFrame.java`，之后处理其余输入文件，再继续 546 配置键、330 菜单资源键、嵌套/计算键、SGF/GIB 与 GTP 语料、旧版动态截图及 GUI/引擎分离性能 |
| T-004 | 未开始 | 配置兼容清单和迁移器 | 以 T-003 当前 596 个活跃字面量叶键及后续发现项为输入，备份、未知键保留、原子保存和回滚测试通过 |
| T-005 | 未开始 | 实现本地质量门脚本 | solution 存在后创建跨平台 `scripts/quality.ps1`，实际执行并传播 format/build/test/smoke/实测失败，Windows/macOS/Linux 均验证非零退出 |
| T-006 | 未开始 | 实现 GitHub Actions | 三平台 CI、fast smoke、real KataGo、security、release 在 GitHub 真实跑通，预期失败能被拦截并记录 run URL |
| T-007 | 未开始 | 实现语义冒烟框架 | 固定 SGF + 确定性 GTP 每 PR，固定哈希真实 KataGo 合并/发布前运行 |
| T-008 | 未开始 | 第一纵切：棋谱查看 | 设置只读导入、SGF、棋盘/分支、保存 round-trip、UI 实测全通过 |
| T-009 | 未开始 | 建立性能参考机器和基线 | 按 §6.5/§6.6 固定硬件、制品、语料与测量次数，记录启动、CPU/RSS、GC、帧/输入时间、泄漏趋势和包体 |
| T-010 | 完成 | 初始化 Git 并连接 GitHub | 已连接公开仓库 `https://github.com/FanhuaAwA/Lizzieyzy-G` 的 `main`，通过已登录 `gh`/HTTPS 推送初始提交 `bc7f646b51dc7222a8e2e48dbd709224afaaa7b9`；branch protection 要求 PR、线性历史、解决讨论并禁止删除/force-push，T-006 在真实工作流存在后再加入必需 checks |
| T-011 | 完成 | 加严低推理 AI、质量门和 GitHub 交付规则 | 已补充写代码前自检、失败矩阵，以及中范围/大范围变更的完整质量门与 commit/push/CI 流程；纯小范围按用户要求豁免完整门 |
| T-012 | 完成 | 最终审计并升级 AI 编程总文档 | 已补齐首次建仓、编码/测试、功能矩阵、专业视觉、实用性、高可用、性能/低占用和供应链规则；最终严格 UTF-8、结构、任务引用和关键契约检查全部 PASS |
| T-013 | 未开始 | 建立专业设计系统与组件展示页 | 用户批准视觉方向；design token、全状态组件、棋盘/图表规范、三平台视觉矩阵和无障碍实测通过 |
| T-014 | 未开始 | 建立可靠性、恢复与长稳体系 | crash/恢复证据、故障注入、100 次棋谱循环、50 次引擎循环和 8 小时 soak 均按 §6.4 通过 |

当前可用范围仅为能启动、显示 19×19 空棋盘并正常关闭的原生新壳；不包含棋谱、设置迁移、引擎或其他旧版功能，不能替代旧版。下一步继续 T-003，盘点 `BrowserFrame.java` 的键盘和 pointer 入口并反向关联矩阵；后续任何部分功能必须新增/拆分 ID，不得藏在“进行中”描述里。

### 12.2 最近验证记录

| 日期 | 范围 | 结果 | 未验证 |
| --- | --- | --- | --- |
| 2026-07-13 | 旧源码静态盘点 | 文件/行数、主要依赖、全局耦合和配置键已静态检查 | Maven 编译/测试、旧发布包运行性能 |
| 2026-07-13 | AI 总文档 | PowerShell 结构检查 PASS：唯一文档 474 行、13 个编号章节、代码围栏成对、10 个任务 ID 唯一、无拆分文档残留；关键技术栈/安全/质量门/冒烟/全量迁移规则均存在 | 所有 .NET 产品门，solution 尚不存在 |
| 2026-07-13 | 低推理 AI 与 GitHub 交付加严 | PowerShell 复核 PASS：13 个编号章节、代码围栏成对、11 个任务 ID 唯一、无尾随空格；中/大变更的 Release build、测试、冒烟、实测、commit、push、Actions 闭环和失败处理均已明确；纯小范围变更豁免完整门 | 纯文档变更，产品编译/冒烟不适用；GitHub 地址尚未提供，无法初始化、commit 或 push |
| 2026-07-13 | 最终 AI 编程可执行性审计 | PowerShell 退出码 0：严格 UTF-8、唯一总文档、0–12 章连续、代码围栏成对、14 个任务 ID 唯一且无悬空引用、无尾随空格、无旧 `.sln` 命令；首次建仓、功能矩阵、C#/异步/资源、测试分层、专业 UI、WCAG、高可用、低占用、长稳、安全工作流和 GitHub 闭环关键契约均存在；官方 .NET 10/Avalonia/WCAG 资料已复核 | 仅文档级变更，产品编译/测试/冒烟/视觉实测不适用；solution 与 `.git` 尚不存在，GitHub URL 尚未提供；T-002–T-010、T-013、T-014 仍未完成 |
| 2026-07-13 | T-010 Git/GitHub 初始化 | 本地 `main` 连接用户确认的公开 `origin`；初始提交 `bc7f646b51dc7222a8e2e48dbd709224afaaa7b9` 已推送且 local/remote SHA 一致；严格 UTF-8、章节 0–12、代码围栏、任务 ID 唯一、尾随空格和秘密模式检查退出码 0；branch protection 要求 PR、线性历史、解决讨论并禁止删除/force-push | solution、产品测试、冒烟与 Actions 尚不存在；必需 status checks 待 T-006 创建并真实验证工作流后加入保护规则 |
| 2026-07-13 | T-002 .NET/Avalonia 基线 | x64 SDK `10.0.103`、官方 `Avalonia.Templates 12.1.0`；六项目 SLNX 和依赖方向已核对；一次非 locked restore 生成六份真实锁文件，此后 locked restore 退出码 0；format verify 0 改动；Release build 0 警告/0 错误；Core 3 + Engine 1 + Desktop headless 1 共 5 项测试全通过；Release 可执行文件真实打开 `LizzieYzy GL` 960×752 窗口，截图确认 19×19 空棋盘后正常关闭并退出；六项目依赖审计未发现已知漏洞；实现提交 `c17873dde901b77637e770c241dbdc3e3037218a` 已推送且远端 SHA 一致，draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/1` 为 OPEN/CLEAN | Windows 本地已验证；macOS/Linux、Actions、性能/长稳、完整无障碍和旧版功能等价不属于 T-002，分别由 T-003、T-006、T-009、T-013、T-014 及后续纵切完成；当前 PR 无 checks，原因是 T-006 尚未建立工作流，无 Actions run URL |
| 2026-07-13 | T-003 旧版可执行基线与首批矩阵 | Apache Maven 3.9.16 ZIP 的 SHA-512 与官方值一致；仓库外隔离副本以 Temurin 21.0.11 执行 `mvn -Dfmt.skip=true test`，1,161 tests、0 failure、0 error、1 个 Windows 条件 skip；原旧源码无 `target`，576 个源文件逐一比对 0 差异，聚合指纹 `4615770949982e1d0742b7e6009be25e3345d97946d98ac243af65e5d98f4f23`；`python scripts/generate_legacy_inventory.py --check` 通过，清单含 276 主 Java、145 测试 Java、596 活跃配置叶键/1,627 引用、37 注释候选键、383 菜单资源键/473 活跃引用；矩阵首批 17 个用例均为 `已盘点`，关联 28 配置键、47 菜单资源键和全部 2 个显式 accelerator；新版 locked restore、format verify、Release build 均退出 0，build 为 0 warning/0 error，5 项测试全通过，Release 窗口再次实测打开 19×19 空棋盘并正常关闭；实现提交 `5598da03fed06f437c68f8d3d1cef6f86c220a19` 已推送，堆叠 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` 以 T-002 分支为 base 且为 OPEN/CLEAN | T-003 未完成：568 个活跃配置叶键和 336 个菜单资源键尚未关联用例，嵌套/计算键、硬编码菜单文字和其他输入绑定尚未归一，完整功能拆分、SGF/GIB 与 GTP 语料、旧版动态界面截图、性能和跨实现验证均待完成；任何新版功能均未因本轮盘点而标为已实现或已验证；当前 PR 无 checks，原因是 T-006 尚未建立工作流，无 Actions run URL |
| 2026-07-13 | T-003 菜单与快捷键反向索引 | 矩阵和生成清单升级到 schema 2；生成器同时识别大小写 `Menu.*`/`menu.*`，383 个活跃菜单资源键/473 引用中 47 个反向关联现有 17 行矩阵，`Shift+O` 与仅 Windows 的 `Alt+O` 两个显式 accelerator 均关联；伪菜单键和伪快捷键 mutation 均被拒绝；与 HEAD 做语义比较确认来源指纹、596 配置键索引和 145 个测试文件清单未变；`python scripts/generate_legacy_inventory.py --check`、x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error，Release 窗口实测显示 19×19 空棋盘后正常关闭；增量提交 `8736e2b0f28a54fae7bfd545565f514bc9377b7e` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：336 个菜单资源键、硬编码菜单文字和其他输入绑定尚未关联；本轮无产品路径变化，性能、DPI、无障碍、故障恢复、长稳和安装包验证不适用；Actions 由 T-006 跟踪，当前无 run URL |
| 2026-07-13 | T-003 硬编码菜单与输入 case 反向索引 | 矩阵和生成清单升级到 schema 3；`Menu.java` 12 个活跃硬编码菜单字面量全部生成，6 个语言项关联 `SETTINGS-LANGUAGE-001`；`Input.java` 54 个 `keyPressed` 与 2 个 `keyReleased` `VK_*` case 全部生成，15 个 case 关联现有矩阵行，并记录局部 modifier 检查但不伪称完整组合语义；伪菜单字面量和伪输入 case mutation 均被拒绝，双向映射/唯一性断言通过；与 HEAD 语义比较确认来源指纹、596 配置键、383 菜单资源键和 2 个 accelerator 未变；`python scripts/generate_legacy_inventory.py --check`、x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 窗口实测显示 19×19 空棋盘后正常关闭；实现提交 `d976c852b94843258503ec4b3b0a6811af18dd37` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：568 配置键、336 菜单资源键、6 个菜单字面量和 41 个输入 case 尚未关联工作流；modifier/fall-through/动作组合及鼠标输入仍未归一；本轮无产品路径变化，性能、DPI、无障碍、故障恢复、长稳和安装包验证不适用；Actions 由 T-006 跟踪，当前无 run URL |
| 2026-07-13 | T-003 详细工具栏、更新与隐私动作矩阵 | 新增 `UI-DETAILED-TOOLBAR-001`、`UPDATE-WINDOWS-001`、`PRIVACY-CLEAR-DATA-001`，20 行矩阵均为 `已盘点`；12/12 个硬编码菜单字面量全部反向关联，配置叶键关联 28→34、菜单资源键关联 47→48；静态证据确认 `windows-update-last-check-date`/`windows-update-ignored-version` 为常量间接键，尚未计入 596 字面量口径；清除个人数据四键中三键为 remove-only，且旧版 `Config.save()` 失败后仍显示成功，目标行为明确禁止照搬；伪标签 mutation、双向映射、HEAD 语义比较、独立安全 review 和秘密扫描通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 窗口实测显示 19×19 空棋盘后正常关闭；实现提交 `ddfc406ac68ba707bbbcf5b42810ba49c23222e9` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：562 配置键、335 菜单资源键和 41 个输入 case 尚未关联工作流，计算/嵌套键与精确输入动作仍未归一；未执行旧版真实更新、下载或清除数据，相关动态行为尚未验证；本轮无产品路径变化，性能、DPI、无障碍、故障恢复、长稳和安装包验证不适用；Actions 由 T-006 跟踪，当前无 run URL |
| 2026-07-13 | T-003 `Input.java` 精确输入绑定矩阵 | 矩阵和生成清单升级到 schema 4；轻量静态解析器把 56 个 `keyPressed`/`keyReleased` case 展开为 162 条互斥路径，记录 Control/Meta 差异、条件求值及方法副作用、执行语句、无动作分支、case 链和按键后统一刷新，162/162 均反向关联 40 行 `已盘点` 矩阵；配置关联 34→36，菜单资源键维持 48，菜单字面量和 accelerator 继续全覆盖；独立 review 纠正 N 默认分支的人机新对局归属，并登记分享空实现、在线入口吞异常、临时棋盘恢复疑似错误及 sleep 轮询缺陷；伪绑定 mutation 被拒绝，来源指纹、596 配置键、菜单提取和 Java 测试清单语义比较通过，只有预期的 fall-through modifier 修正；严格 UTF-8、生成新鲜度、diff/秘密/动态执行审计通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 窗口实测显示 19×19 空棋盘后正常关闭；实现提交 `8dc40e96ebdb45c6def4c3f0471c25373ad0f327` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：560 配置键、335 菜单资源键、其他键监听器和鼠标绑定、嵌套/计算键、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证均待完成；本轮未修改产品代码或旧 Java，未执行旧版真实更新、下载、清除数据或在线同步；Actions 由 T-006 跟踪，当前无 run URL |
| 2026-07-13 | T-003 独立主棋盘精确键绑定 | 矩阵和生成清单升级到 schema 5；复用同一轻量解析器纳入 `InputIndependentMainBoard.java` 的 56 个 case/162 条路径，与主 `Input.java` 合计 112/112 case、324/324 路径全部反向关联原有 40 行 `已盘点` 矩阵；两个来源的 case/路径 ID 一一对应且工作流映射相同，逐项比较锁定恰好 8 条实现差异，涵盖独立 renderer 方向导航、Page 键仍走主 renderer、计数清理、独立 R 重放和 Alt+7 fall-through；原 `Input.java` 全部生成记录、来源指纹、596 配置键、菜单提取和 Java 测试清单与 HEAD 一致，伪造来源绑定 mutation 被拒绝；严格 UTF-8、生成新鲜度、机械扩展边界、完整 diff、秘密和动态执行独立审计通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `cf5cf53c01290f48086767789d56657fad183c5f` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：另有 18 个键事件文件、30 个鼠标事件文件、560 配置键、335 菜单资源键、嵌套/计算键、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，因此独立主棋盘新版功能、DPI、无障碍和动态等价均未验证，现有空壳冒烟不能证明这些功能；未执行旧版在线、下载、更新或用户数据操作；Actions 由 T-006 跟踪，当前无 run URL |
| 2026-07-13 | T-003 子棋盘键盘与 pointer 输入 | 矩阵和生成清单升级到 schema 6；复用同一轻量解析器并仅补充空 `keyReleased`、`return` 终止及 pointer 方法采集，纳入 `InputIndependentSubboard.java` 的 3 case/5 键路径与 6 事件/6 pointer 路径、`InputSubboard.java` 的 2 case/4 键路径与 6 事件/13 pointer 路径；总计 117/117 case、333/333 键路径、12/12 pointer 事件和 19/19 pointer 路径全部反向关联 42 行 `已盘点` 矩阵；新增 `ENGINE-GAME-CONTROL-001`、`BOARD-SUBBOARD-INPUT-001`，主副棋盘滚轮的早退、8 条条件路径和显式空操作均保留；伪 binding 与整行漏映射 mutation 均被拒绝；旧两个键源 324 条记录、来源指纹、配置、菜单和 Java 测试清单与 HEAD 一致，完整 diff、严格 UTF-8、秘密、动态执行和旧基准只读 review 通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `70f78ae2b6a1fe4916ae04c6f0a8a61abdd037d2` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：另有 16 个键事件文件、28 个鼠标事件文件、560 配置键、335 个菜单资源键、嵌套/计算键、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，因此新版子棋盘输入、DPI、无障碍和动态等价均未验证，空壳冒烟不能证明这些功能；未执行旧版在线、下载、更新或用户数据操作；Actions 由 T-006 跟踪，当前无 run URL |
| 2026-07-13 | T-003 FloatBoard 键盘与 pointer 输入 | 矩阵和生成清单升级到 schema 7；复用同一轻量解析器，仅补充无 switch 的顶层按键分发、块状 `for` 原子记录和 FloatBoard 局部布尔赋值追踪，纳入 11 case/16 条键路径及鼠标按下、离开、滚轮、移动 4 事件/20 条可达 pointer 路径；总计 128/128 case、349/349 键路径、16/16 pointer 事件和 39/39 pointer 路径全部反向关联 43 行 `已盘点` 矩阵，新增 `BOARD-FLOAT-INPUT-001`；伪 binding 与整行漏映射 mutation 均被拒绝；旧四个键源、两个子棋盘 pointer 源、来源指纹、配置、菜单和 Java 测试清单与 HEAD 一致；完整 diff、严格 UTF-8、秘密、动态执行和旧基准只读 review 通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `2b658119131641850f1697a64a2bba87bddabc99` 与验证台账提交 `90254295bdeeb5f261f554376de6a168df6a479e` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2`，当时 local/remote SHA 一致且 PR 为 OPEN/CLEAN、无 checks/Actions run | T-003 仍未完成：另有 15 个键事件文件、27 个鼠标事件文件、560 配置键、335 个菜单资源键、嵌套/计算键、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，FloatBoard 新版输入、外部读盘动态等价、DPI、无障碍均未验证，空壳冒烟不能证明这些功能；未执行旧版在线、下载、更新或用户数据操作；Actions 由 T-006 跟踪，当前无 run URL |
| 2026-07-13 | T-003 AnalysisFrame 键盘与 pointer 输入 | 矩阵和生成清单升级到 schema 8；复用轻量解析器并仅补充同文件同事件监听器序号、`mouseDragged` 和 try/catch 原子记录，纳入 AnalysisFrame 表格 6 case、窗口 4 case 共 10 条键路径，以及移动/拖动/滚轮/离开/点击/表头释放 6 事件/18 条 pointer 路径；总计 138/138 case、359/359 键路径、22/22 pointer 事件和 57/57 pointer 路径全部反向关联 44 行 `已盘点` 矩阵，新增 `UI-ANALYSIS-FRAME-001`，并把 `anaframe-use-mousemove`、`suggestions-always-ontop` 纳入配置映射；伪 binding 与整行漏映射 mutation 均被拒绝，旧输入记录、来源指纹、菜单和 Java 测试清单与 HEAD 一致；严格 UTF-8/LF、生成新鲜度、JSON/Python、完整 diff、秘密、动态执行、依赖漏洞和旧基准只读 review 通过；汇总断言首次因 PowerShell 管道内中文源码字面量编码不一致失败，改用矩阵自身状态常量后复跑通过，仓库数据未修改；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `402676ba91656c66d0821b3197c39b1465a55d8d` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：另有 14 个键事件文件、26 个鼠标事件文件、558 配置键、335 个菜单资源键、嵌套/计算键、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，因此 AnalysisFrame 新版交互、动态等价、DPI、无障碍和真实引擎候选均未验证，空壳冒烟不能证明这些功能；未执行旧版在线、下载、更新或用户数据操作；Actions 由 T-006 跟踪，当前无 run URL；唯一推荐下一步为盘点 `DrawPainting.java` |
| 2026-07-14 | T-003 DrawPainting 键盘与 pointer 输入 | 矩阵和生成清单升级到 schema 9；现有解析器无需新增分支，仅登记 DrawPainting 键盘和 pointer 来源，纳入 1 个 Escape case/1 条键路径，以及释放/拖动/移动 3 事件/5 条 pointer 路径；总计 139/139 case、360/360 键路径、25/25 pointer 事件和 62/62 pointer 路径全部反向关联 45 行 `已盘点` 矩阵，新增 `UI-FREE-DRAWING-001`，并关联 `last-painting-color` 与 `Menu.drawPainting.toolTipText`；静态下游保留任意鼠标按键拖动、仅左键提交非空笔迹、两条 release 空路径、空 mouseMoved、颜色/撤销/清空/关闭动作和 DrawPainting 自身不调用 Config.save 的事实；伪 binding 与整行漏映射 mutation 均被拒绝，旧输入记录、来源指纹、既有配置/菜单记录和 Java 测试清单与 HEAD 一致；严格 UTF-8/LF、生成新鲜度、JSON/Python、完整 diff、秘密、动态执行、依赖漏洞和旧基准只读 review 通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `d84c41125c4847b7edd6b94c0ffcf07324eb7b4c` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：另有 13 个键事件文件、25 个鼠标事件文件、557 配置键、334 个菜单资源键、嵌套/计算键、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，因此新版自由绘图、动态等价、焦点、多 DPI、无障碍、资源缺失降级和颜色重启持久化均未验证，空壳冒烟不能证明这些功能；Actions 由 T-006 跟踪，当前无 run URL；唯一推荐下一步为盘点 `ChooseMoreEngine.java` |
| 2026-07-14 | T-003 ChooseMoreEngine 键盘与 pointer 输入 | 矩阵和生成清单升级到 schema 10；现有解析器无需新增分支，仅登记 ChooseMoreEngine 的空 `keyPressed` 来源和 pointer 来源，键总数保持 139/139 case、360/360 路径，新增点击/表头释放 2 事件/6 条 pointer 路径，总计 27/27 事件、68/68 路径全部反向关联 45 行 `已盘点` 矩阵；扩展 `ENGINE-LIFECYCLE-001`，静态下游保留配置至少 21 个引擎才出现更多引擎入口、模式 1/2 切主/副引擎、非右键且非双击选择、双击或右击立即切换、无效单元格与空表头/键监听无动作、未选择确认先隐藏再提示及点击异常只打印堆栈的事实；完整 diff review 纠正“仅左键选择”为旧版真实的“任何非右键且点击次数不等于 2”；伪 binding 与整事件漏映射 mutation 均被拒绝，旧输入记录、来源指纹、配置、菜单和 Java 测试清单与 HEAD 一致；严格 UTF-8/LF、生成新鲜度、JSON/Python、秘密、动态执行、依赖漏洞和旧基准只读 review 通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `dc4c05a5dd088ef9ba8047a444764486031a9917` 已推送到 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：另有 12 个键事件文件、24 个鼠标事件文件、557 配置键、334 个菜单资源键、嵌套/计算键、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，因此新版更多引擎窗口、动态切换、焦点、多 DPI、无障碍、错误恢复和真实引擎进程均未验证，空壳冒烟不能证明这些功能；Actions 由 T-006 跟踪，当前无 run URL；唯一推荐下一步为盘点 `LoadEngine.java` |
| 2026-07-14 | T-003 LoadEngine 键盘与 pointer 输入 | 矩阵和生成清单升级到 schema 11；现有解析器无需新增分支，仅登记 LoadEngine 的空 `keyPressed` 来源和 pointer 来源，键总数保持 139/139 case、360/360 路径，新增点击/表头释放 2 事件/4 条 pointer 路径，总计 29/29 事件、72/72 路径全部反向关联 45 行 `已盘点` 矩阵；扩展 `ENGINE-LIFECYCLE-001` 并关联 `autoload-default`、`autoload-last`、`autoload-empty`、`last-engine`，静态下游保留点击次数不等于 2 时任意按键按有效行选择、点击次数等于 2 时要求有效行列并先隐藏再启动、无效区域与空表头/键监听无动作、未选择确认保持可见、直接无引擎启动、四种下次启动策略、冲突标志优先级、Escape/退出/关窗终止应用、正常退出条件保存及异常只打印堆栈等事实；伪 binding 与整事件漏映射 mutation 均被拒绝，旧来源、配置引用、菜单、Java 测试、输入记录和其余 44 行矩阵与 HEAD 一致；严格 UTF-8/LF、生成新鲜度、JSON/Python、完整 diff、秘密、动态执行、依赖漏洞和旧基准只读 review 通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `1a64b70119573dd5ae110cee66d7377d2ca5364c` 位于 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：另有 11 个键事件文件、23 个鼠标事件文件、553 配置键、334 个菜单资源键、嵌套/计算键、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，因此新版启动引擎选择器、真实进程、动态等价、焦点、多 DPI、无障碍、错误恢复及重启持久化均未验证，空壳冒烟不能证明这些功能；未执行旧版在线、下载、更新或用户数据操作；Actions 由 T-006 跟踪，当前无 run URL；唯一推荐下一步为盘点 `OtherPrograms.java` |
| 2026-07-14 | T-003 OtherPrograms 外部程序快捷链接 | 矩阵和生成清单升级到 schema 12；现有解析器无需新增分支，仅登记 OtherPrograms 的空 `keyPressed` 来源和 pointer 来源，键总数保持 139/139 case、360/360 路径，新增无条件点击与空表头释放 2 个事件/2 条路径，总计 31/31 事件、74/74 路径全部反向关联 46 行 `已盘点` 矩阵；新增 `EXTERNAL-PROGRAMS-001`，关联 `program-command-list`、`program-name-list`、`show-quick-links`、`Menu.quickLinks`、`Menu.editProgram`，静态下游保留固定 30 行表格、压缩并行数组、空槽/远端空白行重复追加、正常退出才持久化、隐藏菜单时编辑入口不可达、非 Windows 文件扫描隐藏面板、无 shell 参数列表启动及失败消息不显示等事实，并明确目标版的路径校验、错误反馈、原子保存和进程生命周期边界；伪 binding 与整事件漏映射 mutation 均被拒绝，与 HEAD 比较确认除预期 3 个配置映射、2 个菜单映射和新输入源外语义一致；严格 UTF-8/LF、生成新鲜度、JSON/Python、完整 diff、秘密、动态执行、旧基准只读和六项目依赖漏洞 review 通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5 项 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `826c259802b14ba3a05d0e09846ed0566e56ee77` 位于 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：另有 10 个键事件文件、22 个鼠标事件文件、550 配置键、332 个菜单资源键、嵌套/计算键、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，因此新版外部程序管理/启动、动态等价、焦点、多 DPI、无障碍、错误恢复、跨平台文件选择和重启持久化均未验证，空壳冒烟不能证明这些功能；未执行旧版用户配置命令、真实外部进程、在线或下载动作；Actions 由 T-006 跟踪，当前无 run URL；唯一推荐下一步为盘点 `TencentKifuDownload.java` |
| 2026-07-14 | T-003 TencentKifuDownload 在线棋谱 | 矩阵和生成清单升级到 schema 13；现有解析器无需新增分支，仅登记 TencentKifuDownload 的查询框 `Enter` 和表格 `mouseClicked` 来源，新增 1 个 case/1 条键路径及 1 个事件/2 条 pointer 路径，总计 140/140 case、361/361 键路径、32/32 pointer 事件和 76/76 pointer 路径全部反向关联 46 行 `已盘点` 矩阵；扩充 `ONLINE-TENCENT-001`，配置映射 46→50、菜单资源映射 51→52，关联工具栏入口、腾讯三项自身配置、共享代理三键、`fox-after-get` 兼容回退和 `auto-quick-analyze-on-load`。静态下游确认固定 HTTPS 接口每批取 100/每页显示 25、任意鼠标按键双击有效单元格、成功非空列表才保存最多 8 项最近搜索、详情 SGF 直接替换当前棋盘且不写本地棋谱、条件式静默快速全盘分析、三种载入后动作、最多 3 次 HTTP 尝试，以及无取消、隐藏不终止、旧回调串入新查询、空白/缺字段成功响应永久 busy、非成功状态仍读全文、响应/JSON/SGF 无上限、完整错误回显和固定 120ms 收尾等迁移边界；旧测试证据已改为真实覆盖范围，不再声称完成请求/下载测试。伪 binding 与整事件漏映射 mutation 均被拒绝；整事件 mutation 首次因临时验证脚本按 CRLF 替换而未实际变异，改用 LF 并增加变异文本断言后按预期失败，仓库数据未改。与 HEAD 语义比较确认其余 45 行、来源身份、596 配置/383 菜单提取、145 个测试文件和所有既有输入记录不变；严格 UTF-8/LF、生成新鲜度、JSON/Python、完整 diff、秘密、动态执行、旧基准只读和六项目依赖漏洞 review 通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5/5 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `2d3a4441e4c51beea15fa4b26b3872b124f49b2e` 位于 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：另有 9 个键事件文件、21 个鼠标事件文件、546 配置键、331 个菜单资源键、嵌套/计算键、受控 HTTP/SGF 夹具、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，未执行真实腾讯网络请求、下载、用户配置/文件写入或旧版 GUI，因此新版腾讯功能、动态等价、取消/超时/竞态/大小限制、焦点、多 DPI、无障碍和真实引擎分析均未验证，空壳冒烟不能证明这些功能；Actions 由 T-006 跟踪，当前无 run URL；唯一推荐下一步为盘点 `FoxKifuDownload.java` |
| 2026-07-14 | T-003 FoxKifuDownload 在线棋谱 | 矩阵和生成清单升级到 schema 14；现有解析器无需新增分支，仅登记 FoxKifuDownload 的查询框 `Enter` 和表格 `mouseClicked` 来源，新增 1 个 case/1 条键路径及 1 个事件/3 条 pointer 路径，总计 141/141 case、362/362 键路径、33/33 pointer 事件和 79/79 pointer 路径全部反向关联 46 行 `已盘点` 矩阵；扩充 `ONLINE-FOX-001`，菜单资源映射 52→53，关联菜单、详细工具栏、底部工具栏、野狐三项自身配置、`read-komi`、`auto-quick-analyze-on-load` 与共享代理三键。静态下游确认昵称/uid 两段查询、每批至多 100/每页 25、任意鼠标按键双击、成功非空列表才保存最多 8 项最近搜索、SGF 主线/窗口化残缺分支恢复、内存棋盘替换与条件式快速分析，并登记两个明文 HTTP 详情 CGI、最多 9 次端点尝试、无取消/隐藏不终止、越界配置构造失败、畸形分页提交后不回滚、无界响应/递归 SGF/计算、原始响应回显与固定 120ms 收尾等不得迁移的风险；目标行为明确为 HTTPS-only、可取消、代次/游标事务隔离、资源上限和确定性收尾。伪 binding 与整事件漏映射 mutation 均被拒绝；与实现提交前 HEAD 做语义比较确认其余 45 行、来源身份、596 配置/383 菜单提取、145 个测试文件和全部既有输入记录不变；严格 UTF-8/LF、生成新鲜度、JSON/Python、完整 diff、秘密、动态执行、旧基准只读和六项目依赖漏洞 review 通过；x64 SDK 10.0.103 locked restore、format verify、Release `/warnaserror` build 和 5/5 tests 均退出 0，build 为 0 warning/0 error；Release 实图确认 `LizzieYzy GL` 19×19 空棋盘并正常退出；实现提交 `2ff509b71dbd999beb9ee61d29342a42cecdc59b` 位于 draft PR `https://github.com/FanhuaAwA/Lizzieyzy-G/pull/2` | T-003 仍未完成：另有 8 个键事件文件、20 个鼠标事件文件、546 配置键、330 个菜单资源键、嵌套/计算键、受控 HTTP/SGF 夹具、跨实现 SGF/GIB 与 GTP 语料、旧版动态截图、性能和跨平台验证；本轮未修改产品代码或旧 Java，未执行真实野狐网络请求、下载、用户配置/文件写入或旧版 GUI，因此新版野狐功能、动态等价、取消/超时/竞态/大小限制、焦点、多 DPI、无障碍和真实引擎分析均未验证，空壳冒烟不能证明这些功能；Actions 由 T-006 跟踪，当前无 run URL；唯一推荐下一步为盘点 `BrowserFrame.java` |

### 12.3 更新规则

- 开始任务：在计划中引用任务 ID 和本次最小完成条件。
- 任务 ID 永不复用或改义；新架构/安全/兼容决策必须写入对应任务或最近验证记录，不能只存在于聊天上下文。
- 只有完成条件和全部适用质量门有证据时，状态改“完成”。
- 部分完成：写清可用/不可用范围、用户影响、下一步、验证方法；必要时拆分新 ID。
- 阻塞：写具体缺失物，如“缺真实 KataGo 测试制品 SHA-256”，不能只写“环境问题”。
- 验证：保存命令、退出码、测试数量、环境、冒烟语义；GitHub 保存 run URL。
- 完成历史可压缩，但不能删除仍影响兼容、用户数据失败恢复或未完成工作的事实。

### 12.4 交接模板

```text
日期/任务 ID：
变更级别与触发的安全边界：
目标与完成条件：
功能等价矩阵行/配置键：
实际修改文件：
已完成（行为证据）：
未完成/半成品（用户影响）：
质量门命令与结果：
冒烟/功能实测：
性能与安全 review：
视觉/无障碍/可靠性证据路径：
Git 分支/commit SHA/远端/PR/Actions URL：
风险/阻塞：
下一步唯一推荐动作：
```

没有执行的栏填写“未执行：具体原因”，不得省略或改写为通过。

AI 对用户交付至少说明：实际完成及文件、运行的质量门及结果、未完成/未验证及原因、关闭或新增的任务 ID。
