# AI-Driven Embedded Systems Development Environment

**Author:** Kai-Hao Yang
**Target Platform:** NXP i.MX93 (Heterogeneous Multicore: Cortex-A55 + Cortex-M33)
**Core Tools:** Claude 3 API, LangChain, Keil MDK, Yocto Project

## Project Overview

This project aims to integrate an AI agent into the embedded systems development workflow to automate compiling, flashing, debugging, and testing. It consists of two primary tasks:

1. **Task 1 (MCU / Cortex-M):** Automate IDE tools (Keil MDK & J-Link) using Python scripts and allow the AI to trigger builds and analyze debug logs.
2. **Task 2 (MPU / Cortex-A):** Fine-tune an AI agent (via RAG) to understand the Board Support Package (BSP), control the Yocto build system remotely, and deploy images to the target board.

## Phase 1: Knowledge Base (RAG) Setup

This phase establishes the foundational "memory" for the AI Agent by creating a Vector Database populated with specific hardware and software documentation.

### Prerequisites

* Python 3.10+
* Anthropic API Key (`ANTHROPIC_API_KEY`)
* Required Documents (Place in `./docs` directory):
  * NXP i.MX93 Reference Manual
  * Yocto Project Documentation
  * Keil MDK CLI Reference

### Installation

1. Create and activate the virtual environment:
   ```bash
   python3.10 -m venv venv
   .\venv\Scripts\activate   # Windows
   # source venv/bin/activate # macOS/Linux

   pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt  
