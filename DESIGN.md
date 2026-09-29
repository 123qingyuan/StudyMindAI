---
name: StudyMind 2.0
description: 清晰、安静的本地学习工作台
colors:
  primary: "#5558c9"
  action: "#4d50bb"
  canvas: "#f3f5f8"
  surface: "#ffffff"
  ink: "#202632"
  muted: "#626d80"
  dark-canvas: "#10151f"
  dark-surface: "#191f2b"
  dark-ink: "#e7ebf2"
  dark-muted: "#9ba8bb"
  dark-primary: "#acb0ff"
  dark-action: "#6669d8"
typography:
  headline:
    fontFamily: "Segoe UI Variable, Segoe UI, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 750
    lineHeight: 1.35
  body:
    fontSize: "14px"
    lineHeight: 1.6
  label:
    fontSize: "12px"
rounded:
  control: "8px"
  panel: "12px"
spacing:
  small: "8px"
  medium: "16px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
---
# Design System: StudyMind 2.0

## Overview
**Creative North Star: "学习工作台"**
以真实记录和阅读内容为中心。保留品牌星芒与书本标识，用蓝灰中性色、克制靛蓝操作色替代浅紫铺底。Windows 系统字栈承担 Operate 界面，不加载外部字体。

## Colors
`frontend/src/tokens.css` 是颜色唯一实现来源。每个语义角色有 light/dark 对；操作背景与文字链接颜色分离，避免深色高亮文字色被误用为按钮背景。Element Plus 浮层在根元素继承同一套变量。

## Typography
主标题 28px、面板标题 16px、正文 14px、辅助信息 12px；图表密集日期使用 10px。统计使用等宽数字，不用伪统计撑版面。

## Layout
236px 侧栏、62px 顶栏、最大 1280px 内容；窄于 860px 收起导航，640px 以下任务、卡片和详情纵向排列。统计总览使用连续分栏而非四张高亮卡片。资料与知识空间保留主从布局。

## Elevation & Depth
底色、侧栏、内容、浮层逐层分离；内容面板只有轻阴影。浮层使用 18px 垂直偏移、48px 模糊阴影，不用装饰玻璃模糊。低强度背景色轮换保留，减少动态效果时停用动画。

## Shapes
主要面板 12px，按钮 8px，细边框；控件宽度服从内容容器。原有 logo SVG 不反色、不重画。

## Components
- ThemePicker 在登录、顶栏与设置复用；三模式持久化。HTML 引导脚本先于 Vue 应用外观，系统偏好变化实时响应。
- PageHeader 只显示标题、说明和动作，去掉重复副标题。
- 输入、选项、错误、空态、Markdown 代码、图表与弹窗使用语义颜色。
- 主操作 40px，移动端至少 44px；可见键盘焦点、Escape 关闭对话框。
- 图表零值不画柱体；背景轨道不再伪装成数值。

## Do's and Don'ts
- Do 保留真实业务、来源、错误与加载状态。
- Do 新组件直接用语义 tokens，而不是叠加暗色补丁。
- Don't 把品牌名当作已验证的模型 ID，或把已保存配置说成已连接。
- Don't 宣传未开放的 AI 出题、AI 计划生成。

限制：本次按 Windows 桌面/响应式 WebView 验收，不声称 macOS HIG 合规；未完成全量自动 WCAG 审计。登录品牌故事的固定深色插画保留，不作为正文颜色规则。
