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
        """Make a request to the GitHub API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method == 'PATCH':
                response = requests.patch(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            return {}
    
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
        Prioritize issues based on various factors
        
        Factors considered:
        - Age of issue (older issues get higher priority)
        - Number of comments (more engagement = higher priority)
        - Labels (e.g., 'bug', 'high-priority')
        - Complexity (estimated by description length and code blocks)
        
        Returns:
            List of issues sorted by priority (highest first)
        """
        prioritized = []
        
        for issue in issues:
            # Calculate priority score
            age_days = (datetime.now() - datetime.strptime(issue['created_at'], 
                                                          '%Y-%m-%dT%H:%M:%SZ')).days
            comments_count = issue['comments']
            
            # Check for priority labels
            labels = [label['name'].lower() for label in issue.get('labels', [])]
            has_bug_label = any('bug' in label for label in labels)
            has_priority_label = any('priority' in label for label in labels)
            has_high_priority = any(('high' in label and 'priority' in label) for label in labels)
            
            # Estimate complexity
            description_length = len(issue['body']) if issue.get('body') else 0
            code_block_count = issue['body'].count('```') // 2 if issue.get('body') else 0
            
            # Calculate priority score
            priority_score = (
                age_days * 0.5 +                  # Age factor
                comments_count * 2 +              # Engagement factor
                (10 if has_bug_label else 0) +    # Bug label bonus
                (5 if has_priority_label else 0) + # Priority label bonus
                (15 if has_high_priority else 0) - # High priority bonus
                (description_length * 0.01) -     # Complexity penalty
                (code_block_count * 2)            # Code complexity penalty
            )
            
            # Add priority score to issue
            issue['priority_score'] = priority_score
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
    parser.add_argument('--repo', required=True, help='GitHub repository (username/repo)')
    parser.add_argument('--token', help='GitHub Personal Access Token')
    parser.add_argument('--action', choices=['list', 'prioritize', 'assigned', 'analyze'], 
                        default='list', help='Action to perform')
    parser.add_argument('--username', help='GitHub username (for assigned issues)')
    parser.add_argument('--issue', type=int, help='Issue number (for analyze action)')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of issues to display')
    
    args = parser.parse_args()
    
    # Initialize agent
    agent = GitHubMCPAgent(args.repo, args.token)
    
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
