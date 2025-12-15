"""
YinQing Agent 增强版使用示例
演示审核机制和快照回溯功能
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from yinqing.core import (
    EnhancedWorkflowEngine,
    create_review_config,
    ReviewConfig
)


# ==================== 示例 1: 基本使用 ====================

async def example_basic():
    """基本使用示例 - 使用默认配置"""
    print("\n" + "=" * 60)
    print("示例 1: 基本使用（默认配置）")
    print("=" * 60)

    # 使用默认配置创建引擎
    engine = EnhancedWorkflowEngine()

    async for response in engine.stream("用Python实现快速排序算法"):
        print(f"[{response['phase']}] {response['content']}")


# ==================== 示例 2: 自定义审核配置 ====================

async def example_custom_review():
    """自定义审核配置示例"""
    print("\n" + "=" * 60)
    print("示例 2: 自定义审核配置")
    print("=" * 60)

    # 创建严格的审核配置
    config = create_review_config(
        enabled=True,           # 启用审核
        review_all=True,        # 审核所有步骤（不只是最终结果）
        threshold=0.8,          # 高质量阈值
        max_retries=5,          # 允许更多重试
        enable_rollback=True    # 启用回溯
    )

    engine = EnhancedWorkflowEngine(review_config=config)

    async for response in engine.stream("分析并比较React和Vue框架的优缺点"):
        phase = response['phase']
        content = response['content']

        # 根据阶段显示不同颜色/格式
        if phase == 'step_complete':
            score = response.get('review_score')
            if score:
                print(f"  [审核] 分数: {score:.2f}")
        elif phase == 'rollback':
            print(f"  [回溯] {content}")
        elif phase == 'error':
            print(f"  [错误] {content}")
        else:
            print(f"[{phase}] {content}")


# ==================== 示例 3: 指定关键步骤 ====================

async def example_critical_steps():
    """指定关键步骤进行审核"""
    print("\n" + "=" * 60)
    print("示例 3: 关键步骤审核")
    print("=" * 60)

    # 只审核特定的关键步骤
    config = ReviewConfig(
        enabled=True,
        review_all_steps=False,
        review_final_only=False,
        critical_steps=[2, 4],  # 只审核步骤2和4
        quality_threshold=0.75,
        max_retries=3,
        enable_rollback=True
    )

    engine = EnhancedWorkflowEngine(review_config=config)

    async for response in engine.stream("创建一个用户注册功能的设计方案"):
        print(f"[{response['phase']}] {response['content']}")


# ==================== 示例 4: 禁用回溯 ====================

async def example_no_rollback():
    """禁用回溯，只进行审核"""
    print("\n" + "=" * 60)
    print("示例 4: 仅审核（禁用回溯）")
    print("=" * 60)

    config = create_review_config(
        enabled=True,
        review_final=True,
        threshold=0.7,
        max_retries=2,
        enable_rollback=False  # 禁用回溯，失败后直接报错
    )

    engine = EnhancedWorkflowEngine(review_config=config)

    async for response in engine.stream("简述机器学习的基本概念"):
        if response.get('is_complete'):
            print(f"\n完成! Trace ID: {response.get('trace_id')}")
        else:
            print(f"[{response['phase']}] {response['content']}")


# ==================== 示例 5: 完全禁用审核 ====================

async def example_no_review():
    """完全禁用审核（行为类似原版）"""
    print("\n" + "=" * 60)
    print("示例 5: 禁用审核（类似原版行为）")
    print("=" * 60)

    config = create_review_config(enabled=False)
    engine = EnhancedWorkflowEngine(review_config=config)

    async for response in engine.stream("写一首关于春天的诗"):
        print(f"[{response['phase']}] {response['content']}")


# ==================== 示例 6: 同步风格调用 ====================

async def example_sync_style():
    """使用同步风格的 run() 方法"""
    print("\n" + "=" * 60)
    print("示例 6: 同步风格调用")
    print("=" * 60)

    config = create_review_config(
        enabled=True,
        review_final=True,
        threshold=0.7
    )

    engine = EnhancedWorkflowEngine(review_config=config)

    # 使用 run() 方法等待完成
    result = await engine.run("解释什么是递归", review_config=config)

    print(f"Trace ID: {result['trace_id']}")
    print(f"总响应数: {len(result['responses'])}")

    final = result['final_response']
    if final:
        print(f"最终状态: {final['phase']}")
        print(f"完成: {final['is_complete']}")


# ==================== 示例 7: 获取详细审核信息 ====================

async def example_detailed_review():
    """获取详细的审核信息"""
    print("\n" + "=" * 60)
    print("示例 7: 详细审核信息")
    print("=" * 60)

    config = create_review_config(
        enabled=True,
        review_all=True,
        threshold=0.7,
        enable_rollback=True
    )

    engine = EnhancedWorkflowEngine(review_config=config)

    async for response in engine.stream("设计一个简单的待办事项API"):
        phase = response['phase']

        if phase == 'step_complete':
            print(f"\n步骤 {response.get('step_id')} 完成: {response.get('step_name')}")
            if response.get('review_score') is not None:
                print(f"  审核分数: {response['review_score']:.2f}")
                print(f"  审核结果: {'通过' if response.get('review_passed') else '未通过'}")

        elif phase == 'final_review':
            print(f"\n最终审核:")
            print(f"  分数: {response.get('review_score', 'N/A')}")
            print(f"  通过: {response.get('review_passed', 'N/A')}")
            if response.get('issues'):
                print(f"  问题: {response['issues']}")
            if response.get('suggestions'):
                print(f"  建议: {response['suggestions']}")

        elif phase == 'complete':
            print(f"\n{'=' * 40}")
            print(f"任务完成!")
            print(f"保存路径: {response.get('saved_path')}")
            print(f"成功步骤: {response.get('successful_steps')}/{response.get('total_steps')}")

        else:
            print(f"[{phase}] {response['content']}")


# ==================== 主函数 ====================

async def main():
    """运行所有示例"""
    print("\n" + "#" * 60)
    print("# YinQing Agent 增强版使用示例")
    print("#" * 60)

    examples = [
        ("基本使用", example_basic),
        ("自定义审核", example_custom_review),
        ("关键步骤审核", example_critical_steps),
        ("禁用回溯", example_no_rollback),
        ("禁用审核", example_no_review),
        ("同步风格", example_sync_style),
        ("详细审核", example_detailed_review),
    ]

    print("\n可用示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\n选择要运行的示例 (输入数字，或 'all' 运行全部，'q' 退出):")

    while True:
        choice = input("> ").strip().lower()

        if choice == 'q':
            break
        elif choice == 'all':
            for name, func in examples:
                try:
                    await func()
                except Exception as e:
                    print(f"示例 '{name}' 出错: {e}")
                print("\n按回车继续...")
                input()
            break
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(examples):
                    name, func = examples[idx]
                    await func()
                else:
                    print("无效选择")
            except ValueError:
                print("请输入数字")
            except Exception as e:
                print(f"出错: {e}")


if __name__ == "__main__":
    asyncio.run(main())
