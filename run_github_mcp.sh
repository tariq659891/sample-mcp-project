#!/bin/bash
# GitHub MCP Agent Runner Script

# Load configuration
REPO=$(jq -r '.github.repository' mcp_config.json)
TOKEN_ENV_VAR=$(jq -r '.github.token_env_var' mcp_config.json)

# Check if GitHub token is set
if [ -z "${!TOKEN_ENV_VAR}" ]; then
    echo "⚠️  Warning: GitHub token not found in environment variable $TOKEN_ENV_VAR"
    echo "Some features may be limited. Set your token with:"
    echo "export $TOKEN_ENV_VAR=your_github_token"
    echo ""
fi

# Function to display help
show_help() {
    echo "GitHub MCP Agent - Model Context Protocol for GitHub"
    echo "======================================================"
    echo "Usage: ./run_github_mcp.sh [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  list             List recent issues"
    echo "  prioritize       Show prioritized issues"
    echo "  recommend        Recommend issues to work on based on your expertise"
    echo "  assigned USER    Show issues assigned to USER"
    echo "  analyze NUMBER   Analyze issue NUMBER in detail"
    echo "  set-expertise    Set your areas of expertise (e.g., python ml diffusion)"
    echo ""
    echo "Options:"
    echo "  --limit N        Limit output to N issues (default: 10)"
    echo "  --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run_github_mcp.sh list"
    echo "  ./run_github_mcp.sh recommend --limit 5"
    echo "  ./run_github_mcp.sh assigned tariq659891"
    echo "  ./run_github_mcp.sh analyze 1"
    echo "  ./run_github_mcp.sh set-expertise python machine-learning diffusion"
    echo ""
}

# Parse command line arguments
COMMAND=$1
shift

LIMIT=10
USERNAME=""
ISSUE_NUMBER=""
EXPERTISE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --limit)
            LIMIT=$2
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            if [ -z "$USERNAME" ] && [ "$COMMAND" = "assigned" ]; then
                USERNAME=$1
            elif [ -z "$ISSUE_NUMBER" ] && [ "$COMMAND" = "analyze" ]; then
                ISSUE_NUMBER=$1
            elif [ "$COMMAND" = "set-expertise" ]; then
                # Collect all remaining arguments as expertise areas
                EXPERTISE="$EXPERTISE $1"
            else
                echo "Unknown option: $1"
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate command
if [ -z "$COMMAND" ]; then
    show_help
    exit 1
fi

# Execute appropriate command
case "$COMMAND" in
    list)
        python github_mcp_agent.py --action list --limit $LIMIT
        ;;
    prioritize)
        python github_mcp_agent.py --action prioritize --limit $LIMIT
        ;;
    recommend)
        echo "Finding recommended issues for you to work on in huggingface/diffusers..."
        python github_mcp_agent.py --action recommend --limit $LIMIT
        ;;
    assigned)
        if [ -z "$USERNAME" ]; then
            echo "Error: Username required for 'assigned' command"
            show_help
            exit 1
        fi
        python github_mcp_agent.py --action assigned --username "$USERNAME" --limit $LIMIT
        ;;
    analyze)
        if [ -z "$ISSUE_NUMBER" ]; then
            echo "Error: Issue number required for 'analyze' command"
            show_help
            exit 1
        fi
        python github_mcp_agent.py --action analyze --issue "$ISSUE_NUMBER"
        ;;
    set-expertise)
        if [ -z "$EXPERTISE" ]; then
            echo "Error: Please provide at least one area of expertise"
            echo "Example: ./run_github_mcp.sh set-expertise python machine-learning diffusion"
            exit 1
        fi
        # Trim leading space
        EXPERTISE="${EXPERTISE## }"
        echo "Setting your expertise areas to: $EXPERTISE"
        python github_mcp_agent.py --expertise $EXPERTISE
        echo "Your expertise has been updated. Run 'recommend' to see issues matching your skills."
        ;;
    *)
        echo "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
