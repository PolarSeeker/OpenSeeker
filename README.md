# OpenSeeker: Democratizing Frontier Search Agents by Fully Open-Sourcing Training Data

<div align="center">
  <a href="https://huggingface.co/papers/2603.15594">
    <img src="https://img.shields.io/badge/Arxiv-OpenSeeker--v1-b31b1b" alt="Arxiv · OpenSeeker-v1"/>
  </a>
  <a href="https://arxiv.org/pdf/2605.04036">
    <img src="https://img.shields.io/badge/Arxiv-OpenSeeker--v2-b31b1b" alt="Arxiv · OpenSeeker-v2"/>
  </a>
  <a href="https://huggingface.co/datasets/OpenSeeker/OpenSeeker-v1-Data">
    <img src="https://img.shields.io/badge/HuggingFace-OpenSeeker__v1__Data-orange" alt="HF Dataset"/>
  </a>
  <a href="https://huggingface.co/OpenSeeker/OpenSeeker-v1-30B-SFT">
    <img src="https://img.shields.io/badge/HuggingFace-OpenSeeker__v1__30B__SFT-yellow" alt="HF Models"/>
  </a>
  <a href="https://huggingface.co/PolarSeeker/OpenSeeker-v2-30B-SFT">
    <img src="https://img.shields.io/badge/HuggingFace-OpenSeeker__v2__30B__SFT-yellow" alt="HF Models"/>
  </a>
</div>

<div align="center">
  <img src="assets/OpenSeekerv2.png" alt="Benchmark Results" width="800"/>
</div>

<div align="center">
  <img src="assets/teaser_benchmarks.png" alt="Benchmark Results" width="800"/>
</div>

## 📰 News

- **2026.05.06** 📣 Our OpenSeeker-v2 achieves state-of-the-art performance across four benchmarks among 30B-scale ReAct-based search agents with simple SFT: **46.0%** on BrowseComp, **58.1%** on BrowseComp-ZH, **34.6%** on Humanity’s Last Exam, and **78.0%** on xbench, surpassing even Tongyi DeepResearch, which is trained with a heavy CPT+SFT+RL pipeline. Our code is coming soon!


- **2026.03.17** 🚀 We open-sourced OpenSeeker-v1 (all data and models). Using **11.7K** training examples, we fine-tuned Qwen3-30B-A3B-Thinking-2507 and achieved scores of **48.4%** on BrowseComp-ZH, **29.5%** on BrowseComp, **74.0%** on xbench-DeepSearch, and **59.4%** on WideSearch.

## Overview

OpenSeeker is an open-source search agent system that democratizes access to frontier search capabilities by fully open-sourcing its training data. This project enables researchers and developers to build, evaluate, and deploy advanced search agents for complex information-seeking tasks.


---
### 🌟 Key Achievement

> **OpenSeeker represents the first work by a purely academic team to achieve state-of-the-art performance on frontier search benchmarks while simultaneously open-sourcing the full training data.**
---

## Quick Start

### Installation

Clone the repository and set up the environment:

```bash
# Clone repository
git clone https://github.com/rui-ye/OpenSeeker.git
cd OpenSeeker

# Create conda environment
conda create --name openseeker python=3.10
conda activate openseeker
pip install -r requirements.txt
```

### Model Setup

Download and deploy the OpenSeeker model:

```bash
# 1. Install git-xet (required for downloading the model)
brew install git-xet
git xet install

# 2. Clone the OpenSeeker model repository
git clone https://huggingface.co/OpenSeeker/OpenSeeker-v1-30B-SFT

# 3. Update MODEL_PATH in run_openseeker.sh to point to the downloaded model directory
# Edit run_openseeker.sh and set MODEL_PATH="/path/to/OpenSeeker-v1-30B-SFT"

# 4. Deploy the model server
bash run_openseeker.sh
```

### Configuration

```bash
# Edit setup_env.sh with your API endpoints and keys
source setup_env.sh
```

### Usage

Generate answers and evaluate results:

```bash
# Generate answers for your dataset
python eval/generate_answer.py \
    --dataset_path /path/to/your/dataset.jsonl \
    --out_dir /path/to/output/directory

# Evaluate the generated results
python eval/eval.py \
    --data_path /path/to/output/directory/result_tool200.jsonl \
    --max_workers 20
```


## Project Structure

```
OpenSeeker/
├── eval/                    # Evaluation scripts
│   ├── eval.py             # Main evaluation script
│   ├── generate_answer.py  # Answer generation script
│   └── prompt.py           # Prompt templates
├── src/                     # Core source code
│   ├── llm_tool_openseeker.py  # LLM tool interface
│   ├── config/             # Configuration files
│   │   └── chat_template.jinja  # Chat template configuration
│   └── tools/               # Tool implementations
│       ├── search.py       # Search tool
│       └── visit.py        # Web visit tool
├── run_openseeker.sh       # Model server startup script
├── setup_env.sh            # Environment variable template
└── README.md               # This file
```

### 📚 Citation
If you find OpenSeeker useful in your research, please consider citing:

```bibtex
@article{du2026openseeker,
  title={OpenSeeker: Democratizing Frontier Search Agents by Fully Open-Sourcing Training Data},
  author={Du, Yuwen and Ye, Rui and Tang, Shuo and Zhu, Xinyu and Lu, Yijun and Cai, Yuzhu and Chen, Siheng},
  journal={arXiv preprint arXiv:2603.15594},
  year={2026}
}

@article{du2026openseekerv2,
  title={OpenSeeker-v2: Pushing the Limits of Search Agents with Informative and High-Difficulty Trajectories},
  author={Du, Yuwen and Ye, Rui and Tang, Shuo and Huang, Keduan and Zhu, Xinyu and Cai, Yuzhu and Chen, Siheng},
  journal={arXiv preprint arXiv:2605.04036},
  year={2026}
}
```

### ⭐ Star History

<a href="https://www.star-history.com/?repos=rui-ye%2FOpenSeeker&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=rui-ye/OpenSeeker&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=rui-ye/OpenSeeker&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=rui-ye/OpenSeeker&type=date&legend=top-left" />
 </picture>
</a>


