# GSoC 2026 Submission Form Fields

## Proposal Title

AI Powered Onboarding Experience for openSUSE Linux Distributions

## Proposal Summary

New openSUSE users face a steep learning curve navigating distribution-specific tools like zypper, YaST, Btrfs/Snapper, and systemd. This project builds a locally-running AI onboarding assistant that pairs a Small Language Model (SLM) with a Retrieval-Augmented Generation (RAG) pipeline over official openSUSE documentation. The assistant detects the user's actual system context (desktop environment, pending updates, failed services, filesystem layout) and grounds every answer in real documentation and real system signals. It runs fully offline after setup, respecting user privacy.

A working proof of concept already exists with local SLM inference (TinyLlama 1.1B via llama-cpp-python), a ChromaDB-backed RAG pipeline, system context detection, CLI and Web UI interfaces, and a benchmarking framework.

Deliverables: (1) production-ready SLM with tiered model support, (2) enhanced RAG pipeline with 4+ documentation sources and tuned retrieval, (3) expanded system context detection covering Btrfs/Snapper, networking, GPU, and locale, (4) jeos-firstboot module for first-boot integration, (5) systemd service with socket activation, (6) RPM packaging via OBS with subpackages for core, docs, and model, (7) security hardening and prompt injection defenses, (8) comprehensive testing across hardware tiers, and (9) blog posts and user documentation.

## Project Size

Large

## Project Technologies

Python, llama.cpp, ChromaDB, Sentence Transformers, LangChain, Bash, systemd, RPM, OBS, Gradio

## Project Topics

AI, Machine Learning, Linux, Onboarding, NLP, RAG, Open Source, Packaging, CLI, System Administration

## GitHub

- **Username:** anujagrawal380
- **URL:** https://github.com/anujagrawal380

## PDF Filename

AIPoweredOnboardingExperienceForOpenSUSELinuxDistributions.pdf
