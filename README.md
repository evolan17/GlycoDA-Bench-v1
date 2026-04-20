# 运行说明



1. 将数据集`glycoforge_benchmark_648`的数据集放在项目的data目录下`GlycoAgentBench\data`

2. 安装环境

3. anaconda创建一个python3.12的环境，然后

   ~~~ bash
   conda activate py312
   
   # 激活虚拟环境
   .\.venv\Scripts\Activate.ps1
   # 下载依赖
   pip install -e ".[analysis_full]"
   pip install -e .
   ~~~

4. 运行方式

   ~~~ bash
    # 第一种测试 -只测试llm一次性生成的workflow
    python -m src.app.run_benchmark `
     --models-dir configs/models `
     --benchmark-config configs\benchmark\glycoforge_648.yaml ` 
     --only-models qwen3.5-35b-a3b.yaml kimi-k2.5.yaml ` # 配置model的文件
     --max-datasets 5 ` # 不加这一行默认跑完glycoforge_648下的所有数据集
     --api-config configs/api.local.yaml `  # 这个是本地配置的api文件 如果是http连接换成对应的配置文件
     --workers 2  # 两个子进程 可以开多个
     
     
    # 第二种测试 -逐步调用llm进行决策
     python -m src.app.run_benchmark `
     --models-dir configs/models `
     --benchmark-config configs/benchmark/glycoforge_648.yaml `
     --only-models qwen3.5-27b.yaml tongyi-xiaomi-analysis-pro.yaml qwen3.6-plus.yaml `
     --max-datasets 30 `
     --stratify-scenarios `
     --planning-mode iterative `  # 逐步决策
     --api-config configs/api.local.yaml `
     --workers 16 `
     --job-retries 2
     
     python -m src.app.run_benchmark \
     --models-dir configs/models \
     --benchmark-config configs/benchmark/glycoforge_648.yaml \
     --only-models stream-server-Qwen35-397B-A17B-Rubric-Judge.yaml \
     --workers 16  \ 
     --job-retries 2

     python -m src.app.run_benchmark \
     --models-dir configs/models \
     --benchmark-config configs/benchmark/glycoforge_648.yaml \
     --only-models stream-server-qwen3-8b-base.yaml \
     --workers 16 --job-retries 2  --planning-mode full
     
     # 远程
     
     
     python -m src.app.run_benchmark `
     --models-dir configs/models `
     --benchmark-config configs/benchmark/glycoforge_648.yaml `
     --api-config configs/api.remote_http.yaml `
     --max-datasets 5 ` # 不加这一行默认跑完glycoforge_648下的所有数据集
     --api-config configs/api.local.yaml `  # 这个是本地配置的api文件 如果是http连接换成对应的配置文件
     --workers 2  # 两个子进程 可以开多个
     
     
     
     python -m src.app.run_benchmark `
     --models-dir configs/models `
     --benchmark-config configs/benchmark/glycoforge_648.yaml `
     --api-config configs/api.remote_http.yaml `
     --max-datasets 30 `
     --stratify-scenarios `
     --planning-mode iterative `  # 逐步决策
     --api-config configs/api.local.yaml `
     --workers 16 `
     --job-retries 2
     
     # 使用 stream-server 远程模型（如 qwen3_8b_zx）
     python -m src.app.run_benchmark \
     --models-dir configs/models \
     --benchmark-config configs/benchmark/glycoforge_648.yaml \
     --only-models stream-server-qwen3-8b.yaml \
     --max-datasets 5 \
     --workers 2  
   ~~~

   

5. 运行结果在`GlycoAgentBench\outputs` 下