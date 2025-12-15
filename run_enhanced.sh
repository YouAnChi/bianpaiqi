#!/bin/bash
# 运行增强版 YinQing Agent（支持审核和回溯）

export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# 显示帮助
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    echo "YinQing Agent 增强版启动脚本"
    echo ""
    echo "用法:"
    echo "  ./run_enhanced.sh                    # 交互模式"
    echo "  ./run_enhanced.sh \"你的任务\"         # 直接执行任务"
    echo "  ./run_enhanced.sh status             # 检查服务状态"
    echo ""
    echo "审核选项:"
    echo "  --review / --no-review               # 启用/禁用审核 (默认启用)"
    echo "  --review-all                         # 审核所有步骤"
    echo "  --threshold 0.8                      # 设置质量阈值"
    echo "  --max-retries 5                      # 设置最大重试次数"
    echo "  --rollback / --no-rollback           # 启用/禁用回溯"
    echo ""
    echo "示例:"
    echo "  ./run_enhanced.sh \"分析Python的优缺点\""
    echo "  ./run_enhanced.sh --review-all \"写一份报告\""
    echo "  ./run_enhanced.sh --threshold 0.8 --max-retries 5 \"复杂任务\""
    exit 0
fi

# 检查状态
if [ "$1" == "status" ]; then
    python3 -m yinqing.main_enhanced status
    exit 0
fi

# 运行增强版
python3 -m yinqing.main_enhanced run "$@"
