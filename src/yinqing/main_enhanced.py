"""
YinQing Agent 增强版 CLI
支持审核机制和快照回溯功能
"""

import asyncio
import click
import os
from dotenv import load_dotenv
from yinqing.core.workflow_enhanced import EnhancedWorkflowEngine, create_review_config
from yinqing.core.reviewer import ReviewConfig
from yinqing.utils.logger import get_logger
from yinqing.utils.config import init_api_key

logger = get_logger(__name__)

# Load .env file
load_dotenv()


@click.group()
def main():
    """YinQing Agent 增强版 CLI - 支持审核和回溯"""
    pass


@main.command()
@click.argument('query', required=False)
@click.option('--review/--no-review', default=True, help='启用/禁用审核机制')
@click.option('--review-all', is_flag=True, help='审核所有步骤（默认只审核最终结果）')
@click.option('--threshold', default=0.7, type=float, help='审核质量阈值 (0-1)')
@click.option('--max-retries', default=3, type=int, help='最大重试次数')
@click.option('--rollback/--no-rollback', default=True, help='启用/禁用回溯机制')
@click.option('--critical-steps', default='', help='关键步骤ID列表，逗号分隔，如: 1,3,5')
def run(query, review, review_all, threshold, max_retries, rollback, critical_steps):
    """
    运行任务（增强版，支持审核和回溯）

    示例:
        yinqing-enhanced run "分析Python的优缺点"
        yinqing-enhanced run --review-all "写一份技术报告"
        yinqing-enhanced run --threshold 0.8 --max-retries 5 "复杂任务"
    """
    init_api_key()

    # Check API Key
    if not os.getenv("GOOGLE_API_KEY"):
        click.echo("Error: GOOGLE_API_KEY environment variable is not set.")
        return

    # 解析关键步骤
    critical = []
    if critical_steps:
        try:
            critical = [int(s.strip()) for s in critical_steps.split(',')]
        except ValueError:
            click.echo("Warning: 无法解析 critical-steps，使用默认值")

    # 创建审核配置
    review_config = create_review_config(
        enabled=review,
        review_all=review_all,
        review_final=not review_all,  # 如果不审核所有，就只审核最终
        critical_steps=critical,
        threshold=threshold,
        max_retries=max_retries,
        enable_rollback=rollback
    )

    # 显示配置信息
    click.echo("\n" + "=" * 60)
    click.echo("YinQing Agent 增强版")
    click.echo("=" * 60)
    click.echo(f"审核机制: {'启用' if review else '禁用'}")
    if review:
        click.echo(f"  - 审核模式: {'所有步骤' if review_all else '仅最终结果'}")
        click.echo(f"  - 质量阈值: {threshold}")
        click.echo(f"  - 最大重试: {max_retries}")
        click.echo(f"  - 回溯机制: {'启用' if rollback else '禁用'}")
        if critical:
            click.echo(f"  - 关键步骤: {critical}")
    click.echo("=" * 60 + "\n")

    # 创建增强版引擎
    engine = EnhancedWorkflowEngine(review_config=review_config)

    async def _run_loop():
        nonlocal query
        while True:
            if not query:
                query = click.prompt("请输入任务 (输入 'exit' 退出)")

            if query.lower() in ['exit', 'quit', 'q']:
                click.echo("Bye!")
                break

            click.echo(f"\n{'=' * 60}")
            click.echo(f"任务: {query}")
            click.echo(f"{'=' * 60}\n")

            try:
                async for response in engine.stream(query, review_config=review_config):
                    _display_response(response)
            except Exception as e:
                click.echo(click.style(f"Error: {e}", fg='red'))
                logger.exception(f"Workflow error: {e}")

            query = None
            click.echo("\n" + "-" * 60 + "\n")

    asyncio.run(_run_loop())


def _display_response(response: dict):
    """格式化显示响应"""
    phase = response.get('phase', 'unknown')
    content = response.get('content', '')
    is_complete = response.get('is_complete', False)

    # 根据阶段选择颜色和图标
    phase_config = {
        'start': ('cyan', '🚀'),
        'parsing': ('blue', '📋'),
        'matching': ('magenta', '🔍'),
        'execution': ('yellow', '⚡'),
        'step_complete': ('green', '✅'),
        'rollback': ('red', '🔄'),
        'final_review': ('cyan', '📝'),
        'complete': ('green', '🎉'),
        'error': ('red', '❌'),
        'progress': ('white', '▶️'),
    }

    color, icon = phase_config.get(phase, ('white', '•'))

    # 构建输出
    output = f"{icon} [{phase.upper()}] {content}"

    # 添加审核信息
    if response.get('review_score') is not None:
        score = response['review_score']
        passed = response.get('review_passed', False)
        score_color = 'green' if passed else 'red'
        output += click.style(f" [审核: {score:.2f}]", fg=score_color)

    # 添加步骤信息
    if response.get('step_id'):
        output += f" (Step {response['step_id']})"

    click.echo(click.style(output, fg=color))

    # 显示额外信息
    if response.get('issues'):
        click.echo(click.style("  问题:", fg='yellow'))
        for issue in response['issues']:
            click.echo(click.style(f"    - {issue}", fg='yellow'))

    if response.get('suggestions'):
        click.echo(click.style("  建议:", fg='cyan'))
        for suggestion in response['suggestions']:
            click.echo(click.style(f"    - {suggestion}", fg='cyan'))

    if is_complete:
        click.echo()
        click.echo(click.style("=" * 60, fg='green'))
        if response.get('saved_path'):
            click.echo(click.style(f"结果已保存: {response['saved_path']}", fg='green'))
        if response.get('trace_id'):
            click.echo(click.style(f"Trace ID: {response['trace_id']}", fg='green'))
        click.echo(click.style("=" * 60, fg='green'))


@main.command()
def status():
    """查看系统状态"""
    click.echo("\n系统状态检查:")
    click.echo("-" * 40)

    # 检查API Key
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        click.echo(click.style("✅ GOOGLE_API_KEY: 已配置", fg='green'))
    else:
        click.echo(click.style("❌ GOOGLE_API_KEY: 未配置", fg='red'))

    # 检查服务端口
    import socket
    ports = {
        10000: "MCP Server",
        10001: "Researcher Agent",
        10002: "Writer Agent",
        10003: "Coder Agent",
        10004: "Data Analyst Agent",
        10005: "Reviewer Agent",
        10006: "Translator Agent",
        10007: "Quality Reviewer Agent",
    }

    click.echo("\n服务状态:")
    for port, name in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()

        if result == 0:
            click.echo(click.style(f"  ✅ {name} (:{port}): 运行中", fg='green'))
        else:
            click.echo(click.style(f"  ❌ {name} (:{port}): 未运行", fg='red'))

    click.echo("-" * 40)


@main.command()
@click.option('--config', type=click.Choice(['default', 'strict', 'lenient']), default='default')
def show_config(config):
    """显示审核配置预设"""
    configs = {
        'default': create_review_config(
            enabled=True,
            review_final=True,
            threshold=0.7,
            max_retries=3,
            enable_rollback=True
        ),
        'strict': create_review_config(
            enabled=True,
            review_all=True,
            threshold=0.85,
            max_retries=5,
            enable_rollback=True
        ),
        'lenient': create_review_config(
            enabled=True,
            review_final=True,
            threshold=0.5,
            max_retries=2,
            enable_rollback=False
        ),
    }

    cfg = configs[config]
    click.echo(f"\n审核配置预设: {config}")
    click.echo("-" * 40)
    click.echo(f"启用审核: {cfg.enabled}")
    click.echo(f"审核所有步骤: {cfg.review_all_steps}")
    click.echo(f"仅审核最终结果: {cfg.review_final_only}")
    click.echo(f"质量阈值: {cfg.quality_threshold}")
    click.echo(f"最大重试次数: {cfg.max_retries}")
    click.echo(f"启用回溯: {cfg.enable_rollback}")
    click.echo("-" * 40)


if __name__ == "__main__":
    main()
