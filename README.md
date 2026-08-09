# 🏙️ CityMind — Urban Intelligence Simulation

> **An AI-driven urban simulation and emergency management platform combining Constraint Satisfaction, Graph Optimization, Genetic Algorithms, Dynamic A\* Pathfinding, and Machine Learning within a unified real-time 3D city environment.**

CityMind is a comprehensive Artificial Intelligence project designed to simulate intelligent urban planning, infrastructure optimization, emergency response, dynamic navigation, and crime-risk analysis within a shared city graph.

The system integrates **five major AI challenges** into one interconnected simulation:

1. 🧩 **City Layout Planning — Constraint Satisfaction Problem (CSP)**
2. 🛣️ **Road Network Optimization — Kruskal's Minimum Spanning Tree (MST)**
3. 🚑 **Ambulance Placement — Genetic Algorithm (GA)**
4. 🧭 **Emergency Routing — Dynamic A\* Search**
5. 🚨 **Crime Risk Prediction — Machine Learning**

Rather than presenting these algorithms as isolated demonstrations, CityMind combines them into a shared urban environment where planning, infrastructure, emergency resources, risk analysis, and routing can interact.

The platform consists of a **Python + FastAPI backend** responsible for simulation and AI computation and a **React + Three.js frontend** responsible for interactive 3D visualization.

---

# 📑 Table of Contents

- [Overview](#-overview)
- [Project Motivation](#-project-motivation)
- [Project Objectives](#-project-objectives)
- [Core AI Challenges](#-core-ai-challenges)
  - [City Layout Planning](#1-city-layout-planning--constraint-satisfaction)
  - [Road Network Optimization](#2-road-network-optimization--kruskals-minimum-spanning-tree)
  - [Ambulance Placement](#3-ambulance-placement--genetic-algorithm)
  - [Emergency Routing](#4-emergency-routing--dynamic-a)
  - [Crime Risk Prediction](#5-crime-risk-prediction--machine-learning)
- [System Architecture](#-system-architecture)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Simulation Pipeline](#-simulation-pipeline)
- [Data Flow](#-data-flow)
- [Frontend Architecture](#-frontend-architecture)
- [Backend Architecture](#-backend-architecture)
- [City Simulation](#-city-simulation)
- [Dynamic Emergency Scenario](#-dynamic-emergency-scenario)
- [Installation](#-installation)
- [Running the Backend](#-running-the-backend)
- [Running the Frontend](#-running-the-frontend)
- [Using the Dashboard](#-using-the-dashboard)
- [API Communication](#-api-communication)
- [Algorithmic Design](#-algorithmic-design)
- [Why Multiple AI Algorithms](#-why-multiple-ai-algorithms)
- [Real-Time Adaptation](#-real-time-adaptation)
- [Shared Graph Environment](#-shared-graph-environment)
- [Visualization](#-visualization)
- [Testing](#-testing)
- [Performance Considerations](#-performance-considerations)
- [Limitations](#-limitations)
- [Future Improvements](#-future-improvements)
- [Educational Value](#-educational-value)
- [Project Scope](#-project-scope)
- [Development Workflow](#-development-workflow)
- [Contributing](#-contributing)
- [Project Status](#-project-status)
- [License](#-license)
- [Conclusion](#-conclusion)

---

# 🌆 Overview

Modern cities are complex interconnected systems.

Urban environments contain:

- Residential areas
- Commercial districts
- Industrial zones
- Roads and transportation networks
- Emergency services
- Hospitals
- Public infrastructure
- High-risk areas
- Dynamic environmental conditions

Managing these systems requires solving many different computational problems.

For example:

> Where should city zones be located?

> How should roads connect different parts of the city?

> Where should ambulances be positioned?

> What is the fastest emergency route?

> What happens when a road becomes blocked or flooded?

> Which parts of the city have elevated crime risk?

These questions require different forms of Artificial Intelligence and algorithmic optimization.

CityMind brings these approaches together into a single simulation.

---

# 🎯 Project Motivation

The primary motivation behind CityMind is to demonstrate how multiple AI techniques can cooperate within a realistic problem domain.

Many AI projects demonstrate one algorithm at a time.

For example:

- One project demonstrates A\*.
- Another demonstrates Genetic Algorithms.
- Another demonstrates Machine Learning.
- Another demonstrates graph optimization.

CityMind takes a different approach.

Instead of keeping these algorithms independent, CityMind places them inside a **shared urban simulation environment**.

The result is a system where:

```text
Planning
   ↓
Infrastructure
   ↓
Risk Analysis
   ↓
Emergency Resource Allocation
   ↓
Dynamic Simulation
   ↓
Adaptive Routing
