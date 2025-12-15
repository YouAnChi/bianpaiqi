import asyncio
import click
import os
from dotenv import load_dotenv
from yinqing.core.workflow import WorkflowEngine
from yinqing.utils.logger import get_logger
from yinqing.utils.config import init_api_key

logger = get_logger(__name__)

# Load .env file
load_dotenv()

@click.group()
def main():
    """YinQing Agent CLI"""
    pass

@main.command()
@click.argument('query', required=False)
def run(query):
    """Run a single task or enter interactive mode."""
    init_api_key()
    
    # Check API Key
    if not os.getenv("GOOGLE_API_KEY"):
        click.echo("Error: GOOGLE_API_KEY environment variable is not set.")
        return

    agent = WorkflowEngine()

    async def _run_loop():
        nonlocal query
        while True:
            if not query:
                query = click.prompt("请输入任务 (输入 'exit' 退出)")
            
            if query.lower() in ['exit', 'quit']:
                break
                
            click.echo(f"\n🚀 开始执行任务: {query}\n")
            
            try:
                async for response in agent.stream(query):
                    click.echo(f"[{'DONE' if response['is_complete'] else 'PROG'}] {response['content']}")
            except Exception as e:
                click.echo(f"Error: {e}")
            
            query = None # Reset for next loop
            click.echo("\n------------------------------------------------\n")

    asyncio.run(_run_loop())

if __name__ == "__main__":
    main()
