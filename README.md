# GitHub MCP Agent

This project demonstrates the Model Context Protocol (MCP) for GitHub, providing an agent that can analyze GitHub issues, prioritize them, and assist with code updates.

## Features
- Analyze GitHub issues and prioritize them based on various factors
- Track issues assigned to specific users
- Provide detailed analysis of issues including complexity estimation
- Suggest approaches for solving issues
- Automatically identify relevant files mentioned in issues

## Components
- Simple Python calculator application (app.py)
- GitHub MCP Agent (github_mcp_agent.py)
- Configuration file (mcp_config.json)
- Helper script for running commands (run_github_mcp.sh)

## Getting Started
1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set your GitHub token: `export GITHUB_TOKEN=your_token_here`
4. Run the agent with one of the commands below

## Usage Examples

### List recent issues
```bash
./run_github_mcp.sh list
```

### Prioritize issues
```bash
./run_github_mcp.sh prioritize --limit 5
```

### View issues assigned to a user
```bash
./run_github_mcp.sh assigned tariq659891
```

### Analyze a specific issue
```bash
./run_github_mcp.sh analyze 1
```

### Get help
```bash
./run_github_mcp.sh --help
```

## Configuration

You can customize the behavior of the MCP agent by editing the `mcp_config.json` file. This allows you to:

- Change the target repository
- Configure issue priority rules
- Set up integrations with Slack or email
- Define expertise areas for auto-assignment
- Control automatic actions like labeling and closing stale issues
