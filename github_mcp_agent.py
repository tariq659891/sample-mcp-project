#!/usr/bin/env python3
"""
GitHub MCP Agent - Model Context Protocol for GitHub
This script helps analyze GitHub issues, prioritize them, and assist with code updates.
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

class GitHubMCPAgent:
    """Model Context Protocol Agent for GitHub"""
    
    def __init__(self, repo: str, token: Optional[str] = None):
        """
        Initialize the GitHub MCP Agent
        
        Args:
            repo: GitHub repository in format 'username/repo'
            token: GitHub Personal Access Token (optional)
        """
        self.repo = repo
        self.token = token or os.environ.get('GITHUB_TOKEN')
        self.base_url = f"https://api.github.com/repos/{repo}"
        self.headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
        
        # Verify connection
        self._verify_connection()
    
    def _verify_connection(self) -> None:
        """Verify connection to GitHub API"""
        try:
            response = requests.get(self.base_url, headers=self.headers)
            response.raise_for_status()
            print(f"✅ Successfully connected to GitHub repository: {self.repo}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to GitHub: {e}")
            sys.exit(1)
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict:
        """Make a request to the GitHub API with rate limit handling"""
        url = f"{self.base_url}/{endpoint}"
        try:
            # Check rate limits first
            self._check_rate_limits()
            
            if method == 'GET':
                response = requests.get(url, headers=self.headers)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method == 'PATCH':
                response = requests.patch(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle rate limiting
            if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(reset_time - time.time(), 0) + 1
                print(f"⚠️ Rate limit exceeded. Waiting for {wait_time:.0f} seconds...")
                time.sleep(wait_time)
                return self._make_request(endpoint, method, data)  # Retry after waiting
                
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            return {}
            
    def _check_rate_limits(self) -> None:
        """Check GitHub API rate limits and wait if needed"""
        try:
            response = requests.get("https://api.github.com/rate_limit", headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                core = data.get('resources', {}).get('core', {})
                remaining = core.get('remaining', 1)
                reset_time = core.get('reset', 0)
                
                if remaining <= 5:  # Keep a small buffer
                    wait_time = max(reset_time - time.time(), 0) + 1
                    print(f"⚠️ Only {remaining} API calls remaining. Waiting for {wait_time:.0f} seconds...")
                    time.sleep(wait_time)
        except Exception as e:
            print(f"Warning: Could not check rate limits: {e}")
    
    def get_issues(self, state: str = 'open', sort: str = 'created', 
                  direction: str = 'desc', limit: int = 100) -> List[Dict]:
        """
        Get issues from the repository
        
        Args:
            state: State of issues ('open', 'closed', 'all')
            sort: Sort field ('created', 'updated', 'comments')
            direction: Sort direction ('asc', 'desc')
            limit: Maximum number of issues to return
        
        Returns:
            List of issues
        """
        issues = []
        page = 1
        per_page = min(100, limit)
        
        while len(issues) < limit:
            endpoint = f"issues?state={state}&sort={sort}&direction={direction}&per_page={per_page}&page={page}"
            batch = self._make_request(endpoint)
            
            if not batch:
                break
                
            issues.extend(batch)
            
            if len(batch) < per_page:
                break
                
            page += 1
        
        return issues[:limit]
    
    def prioritize_issues(self, issues: List[Dict]) -> List[Dict]:
        """
        Prioritize issues based on various factors and user expertise
        
        Factors considered:
        - Age of issue (older issues get higher priority)
        - Number of comments (more engagement = higher priority)
        - Labels (e.g., 'bug', 'high-priority', 'good first issue')
        - Complexity (estimated by description length and code blocks)
        - Match with user expertise
        - Contributor friendliness
        
        Returns:
            List of issues sorted by priority (highest first)
        """
        # Load configuration
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_config.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            config = {}
        
        # Get user expertise and preferences
        user_expertise = config.get('agent', {}).get('user_expertise', [])
        high_priority_labels = config.get('github', {}).get('issue_priorities', {}).get('high', [])
        medium_priority_labels = config.get('github', {}).get('issue_priorities', {}).get('medium', [])
        preferred_issue_types = config.get('actions', {}).get('contribution_preferences', {}).get('issue_types', [])
        
        prioritized = []
        
        for issue in issues:
            # Calculate priority score
            age_days = (datetime.now() - datetime.strptime(issue['created_at'], 
                                                          '%Y-%m-%dT%H:%M:%SZ')).days
            comments_count = issue['comments']
            
            # Check for priority labels
            labels = [label['name'].lower() for label in issue.get('labels', [])]
            
            # Label-based priority
            label_score = 0
            for label in labels:
                if any(high_label.lower() in label for high_label in high_priority_labels):
                    label_score += 10
                if any(medium_label.lower() in label for medium_label in medium_priority_labels):
                    label_score += 5
            
            # Contributor friendliness
            contributor_score = 0
            if any('good first issue' in label for label in labels):
                contributor_score += 15
            if any('help wanted' in label for label in labels):
                contributor_score += 10
            if any('beginner' in label for label in labels):
                contributor_score += 8
            
            # Expertise match
            expertise_score = 0
            issue_text = (issue.get('title', '') + ' ' + issue.get('body', '')).lower()
            for expertise in user_expertise:
                if expertise.lower() in issue_text:
                    expertise_score += 5
            
            # Preference match
            preference_score = 0
            for issue_type in preferred_issue_types:
                if any(issue_type.lower() in label for label in labels):
                    preference_score += 8
            
            # Estimate complexity
            description_length = len(issue['body']) if issue.get('body') else 0
            code_block_count = issue['body'].count('```') // 2 if issue.get('body') else 0
            complexity_penalty = (description_length * 0.01) + (code_block_count * 2)
            
            # Calculate priority score
            priority_score = (
                age_days * 0.3 +                # Age factor (reduced weight)
                comments_count * 1.5 +          # Engagement factor
                label_score +                   # Label-based priority
                contributor_score +             # Contributor friendliness
                expertise_score +               # Expertise match
                preference_score -              # Preference match
                complexity_penalty              # Complexity penalty
            )
            
            # Add priority score to issue
            issue['priority_score'] = priority_score
            issue['expertise_match'] = expertise_score > 0
            issue['contributor_friendly'] = contributor_score > 0
            issue['complexity_estimate'] = 'High' if complexity_penalty > 15 else 'Medium' if complexity_penalty > 5 else 'Low'
            prioritized.append(issue)
        
        # Sort by priority score (highest first)
        return sorted(prioritized, key=lambda x: x['priority_score'], reverse=True)
    
    def get_assigned_issues(self, username: str) -> List[Dict]:
        """
        Get issues assigned to a specific user
        
        Args:
            username: GitHub username
            
        Returns:
            List of issues assigned to the user
        """
        issues = self.get_issues(limit=100)
        return [issue for issue in issues if any(
            assignee['login'] == username for assignee in issue.get('assignees', [])
        )]
    
    def analyze_issue(self, issue_number: int) -> Dict:
        """
        Analyze a specific issue in detail
        
        Args:
            issue_number: Issue number
            
        Returns:
            Analysis of the issue including:
            - Basic information
            - Estimated complexity
            - Related files (if mentioned in comments)
            - Suggested approach
        """
        # Get issue details
        issue = self._make_request(f"issues/{issue_number}")
        if not issue:
            return {"error": f"Issue #{issue_number} not found"}
        
        # Get comments
        comments = self._make_request(f"issues/{issue_number}/comments")
        
        # Analyze issue text and comments for file mentions
        all_text = issue.get('body', '') + ' ' + ' '.join([c.get('body', '') for c in comments])
        
        # Simple file pattern detection (can be improved with regex)
        potential_files = []
        for word in all_text.split():
            if ('.' in word and '/' in word) or word.endswith(('.py', '.js', '.html', '.css', '.md')):
                potential_files.append(word.strip('.,()[]{}:;"\''))
        
        # Estimate complexity
        description_length = len(issue.get('body', ''))
        code_blocks = all_text.count('```')
        complexity = "Low"
        if description_length > 500 or code_blocks > 4:
            complexity = "High"
        elif description_length > 200 or code_blocks > 2:
            complexity = "Medium"
        
        return {
            "issue": issue,
            "comments_count": len(comments),
            "complexity": complexity,
            "potential_files": list(set(potential_files)),
            "suggested_approach": self._generate_approach(issue, complexity)
        }
    
    def _generate_approach(self, issue: Dict, complexity: str) -> str:
        """Generate a suggested approach based on the issue"""
        title = issue.get('title', '')
        body = issue.get('body', '')
        
        # This is a simplified approach generator
        # In a real system, you would use LLM or more sophisticated analysis
        if 'bug' in title.lower() or 'fix' in title.lower():
            return f"This appears to be a bug fix with {complexity.lower()} complexity. Recommend debugging and creating a test case first."
        elif 'feature' in title.lower() or 'add' in title.lower():
            return f"This is a feature request with {complexity.lower()} complexity. Recommend starting with requirements clarification and design."
        elif 'documentation' in title.lower() or 'docs' in title.lower():
            return "This is a documentation task. Update relevant docs and ensure examples are working."
        else:
            return f"General task with {complexity.lower()} complexity. Analyze requirements and break down into smaller steps."
    
    def create_comment(self, issue_number: int, comment_text: str) -> Dict:
        """
        Create a comment on an issue
        
        Args:
            issue_number: Issue number
            comment_text: Text of the comment
            
        Returns:
            Response from GitHub API
        """
        return self._make_request(
            f"issues/{issue_number}/comments", 
            method='POST', 
            data={"body": comment_text}
        )
    
    def display_issue_summary(self, issue: Dict) -> None:
        """Print a summary of an issue"""
        print(f"\n{'=' * 80}")
        print(f"Issue #{issue['number']}: {issue['title']}")
        print(f"{'=' * 80}")
        print(f"Status: {issue['state']}")
        print(f"Created: {issue['created_at']}")
        print(f"Author: {issue['user']['login']}")
        
        if issue.get('assignees'):
            assignees = ', '.join([a['login'] for a in issue['assignees']])
            print(f"Assigned to: {assignees}")
        
        if issue.get('labels'):
            labels = ', '.join([l['name'] for l in issue['labels']])
            print(f"Labels: {labels}")
        
        if issue.get('priority_score'):
            print(f"Priority Score: {issue['priority_score']:.2f}")
        
        print(f"\nDescription:")
        print(f"{'-' * 40}")
        print(issue.get('body', 'No description provided')[:300] + 
              ('...' if issue.get('body', '') and len(issue['body']) > 300 else ''))
        print(f"\nURL: {issue['html_url']}")
        print(f"{'=' * 80}\n")

def main():
    """Main function to run the GitHub MCP Agent"""
    parser = argparse.ArgumentParser(description='GitHub MCP Agent')
    parser.add_argument('--repo', help='GitHub repository (username/repo)')
    parser.add_argument('--token', help='GitHub Personal Access Token')
    parser.add_argument('--action', choices=['list', 'prioritize', 'assigned', 'analyze', 'recommend'], 
                        default='list', help='Action to perform')
    parser.add_argument('--username', help='GitHub username (for assigned issues)')
    parser.add_argument('--issue', type=int, help='Issue number (for analyze action)')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of issues to display')
    parser.add_argument('--expertise', nargs='+', help='Your areas of expertise (space-separated)')
    parser.add_argument('--config', help='Path to config file (default: mcp_config.json)')
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = args.config or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_config.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            # Use repo from config if not specified in command line
            if not args.repo:
                args.repo = config.get('github', {}).get('repository')
    except (FileNotFoundError, json.JSONDecodeError) as e:
        if not args.repo:
            print(f"Error: Could not load config file and no repository specified: {e}")
            sys.exit(1)
    
    if not args.repo:
        print("Error: No repository specified. Use --repo or configure in mcp_config.json")
        sys.exit(1)
    
    # Initialize agent
    agent = GitHubMCPAgent(args.repo, args.token)
    
    # Update expertise if provided
    if args.expertise and config:
        if 'agent' not in config:
            config['agent'] = {}
        config['agent']['user_expertise'] = args.expertise
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"Updated expertise in config file: {', '.join(args.expertise)}")
        except Exception as e:
            print(f"Warning: Could not update config file: {e}")
    
    # Perform requested action
    if args.action == 'list':
        issues = agent.get_issues(limit=args.limit)
        print(f"\nFound {len(issues)} issues in {args.repo}:")
        for issue in issues:
            agent.display_issue_summary(issue)
    
    elif args.action == 'prioritize':
        issues = agent.get_issues(limit=100)  # Get more issues for better prioritization
        prioritized = agent.prioritize_issues(issues)
        print(f"\nTop {args.limit} prioritized issues in {args.repo}:")
        for issue in prioritized[:args.limit]:
            agent.display_issue_summary(issue)
    
    elif args.action == 'recommend':
        issues = agent.get_issues(limit=100)  # Get more issues for better prioritization
        prioritized = agent.prioritize_issues(issues)
        
        # Filter for contributor-friendly issues that match expertise
        recommended = [i for i in prioritized if i.get('contributor_friendly', False) and i.get('expertise_match', False)]
        if not recommended:
            # Fall back to just contributor-friendly if no expertise matches
            recommended = [i for i in prioritized if i.get('contributor_friendly', False)]
        if not recommended:
            # Fall back to top prioritized issues if no contributor-friendly issues
            recommended = prioritized
        
        print(f"\nRecommended issues to work on in {args.repo}:")
        print(f"{'=' * 80}")
        print(f"Based on your expertise and issue characteristics, here are the top {min(args.limit, len(recommended))} issues you could contribute to:")
        print(f"{'=' * 80}")
        
        for i, issue in enumerate(recommended[:args.limit], 1):
            print(f"\nRECOMMENDATION #{i}:")
            agent.display_issue_summary(issue)
            print(f"Why this issue: ")
            reasons = []
            if issue.get('contributor_friendly'):
                reasons.append("✅ Marked as good for contributors")
            if issue.get('expertise_match'):
                reasons.append("✅ Matches your expertise")
            if issue.get('complexity_estimate') == 'Low':
                reasons.append("✅ Relatively low complexity")
            if issue.get('priority_score', 0) > 30:
                reasons.append("✅ High priority for the project")
            
            for reason in reasons:
                print(f"  {reason}")
    
    elif args.action == 'assigned':
        if not args.username:
            print("Error: --username is required for 'assigned' action")
            sys.exit(1)
        
        assigned = agent.get_assigned_issues(args.username)
        print(f"\nFound {len(assigned)} issues assigned to {args.username} in {args.repo}:")
        for issue in assigned[:args.limit]:
            agent.display_issue_summary(issue)
    
    elif args.action == 'analyze':
        if not args.issue:
            print("Error: --issue is required for 'analyze' action")
            sys.exit(1)
        
        analysis = agent.analyze_issue(args.issue)
        if 'error' in analysis:
            print(f"Error: {analysis['error']}")
            sys.exit(1)
        
        issue = analysis['issue']
        agent.display_issue_summary(issue)
        
        print(f"Detailed Analysis:")
        print(f"{'=' * 80}")
        print(f"Complexity: {analysis['complexity']}")
        print(f"Comments: {analysis['comments_count']}")
        
        if analysis['potential_files']:
            print(f"\nPotentially related files:")
            for file in analysis['potential_files']:
                print(f"- {file}")
        
        print(f"\nSuggested approach:")
        print(analysis['suggested_approach'])
        print(f"{'=' * 80}\n")

if __name__ == "__main__":
    main()
