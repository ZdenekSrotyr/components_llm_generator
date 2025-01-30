import os
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict
import requests
from dotenv import load_dotenv

# Constants
GITHUB_ALLOWED_PREFIXES = ('ex-', 'wr-', 'components-', 'generic-')
GITHUB_ONLY_PUBLIC_REPOS = True  # True = process only public repos, False = process all repos

BITBUCKET_ALLOWED_PREFIXES = ('kds-team.')
BITBUCKET_ONLY_PUBLIC_REPOS = True  # True = process only public repos, False = process all repos

class RepoProcessor:
    def __init__(self):
        """Initialize with environment variables"""
        load_dotenv()
        self._validate_env_vars()
        self.output_dir = Path("./docs_collection")
        self.output_dir.mkdir(exist_ok=True)

    def _validate_env_vars(self):
        """Validate that all required environment variables are set"""
        required_vars = [
            'GH_TOKEN',
            'GH_ORG',
            'BITBUCKET_USERNAME',
            'BITBUCKET_TOKEN',
            'BITBUCKET_WORKSPACE'
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _filter_repos_by_visibility(self, repos: List[Dict], is_github: bool = True) -> List[Dict]:
        """Filter repositories based on visibility settings"""
        if is_github and not GITHUB_ONLY_PUBLIC_REPOS:
            return repos
        if not is_github and not BITBUCKET_ONLY_PUBLIC_REPOS:
            return repos

        filtered = []
        for repo in repos:
            if is_github:
                is_private = repo['private']
                is_archived = repo.get('archived', False)  # Check if repo is archived
                # Skip public archived repos
                if GITHUB_ONLY_PUBLIC_REPOS and not is_private and not is_archived:
                    filtered.append(repo)
            else:
                # Bitbucket uses 'is_private' directly
                is_private = repo.get('is_private', True)  # Default to private if not specified
                if BITBUCKET_ONLY_PUBLIC_REPOS and not is_private:
                    filtered.append(repo)
        return filtered

    def _get_github_repos(self) -> List[Dict]:
        """Fetch list of repositories from GitHub"""
        headers = {
            'Authorization': f"token {os.getenv('GH_TOKEN')}",
            'Accept': 'application/vnd.github.v3+json'
        }
        
        all_repos = []
        page = 1
        
        while True:
            url = f"https://api.github.com/orgs/{os.getenv('GH_ORG')}/repos?per_page=100&page={page}"
            print(f"Fetching GitHub repos page {page} from: {url}")
            
            response = requests.get(url, headers=headers)
            
            if not response.ok:
                print(f"GitHub API error: {response.status_code} - {response.text}")
                break
            
            page_repos = response.json()
            if not page_repos:  # No more repos
                break
                
            all_repos.extend(page_repos)
            page += 1
        
        filtered_repos = [
            repo for repo in all_repos 
            if any(repo['name'].startswith(prefix) for prefix in GITHUB_ALLOWED_PREFIXES)
        ]
        
        # Apply visibility filter
        filtered_repos = self._filter_repos_by_visibility(filtered_repos, is_github=True)
        
        print(f"Total GitHub repos: {len(all_repos)}")
        print(f"Filtered GitHub repos: {len(filtered_repos)}")
        print("Filtered repo names:", [repo['name'] for repo in filtered_repos])
        
        return filtered_repos

    def _get_bitbucket_repos(self) -> List[Dict]:
        """Fetch list of repositories from Bitbucket"""
        auth = (os.getenv('BITBUCKET_USERNAME'), os.getenv('BITBUCKET_TOKEN'))
        url = f"https://api.bitbucket.org/2.0/repositories/{os.getenv('BITBUCKET_WORKSPACE')}?pagelen=100"
        
        print(f"Fetching Bitbucket repos for workspace: {os.getenv('BITBUCKET_WORKSPACE')}")
        print(f"Using username: {os.getenv('BITBUCKET_USERNAME')}")
        
        all_repos = []
        
        while url:
            print(f"Fetching Bitbucket repos from: {url}")
            response = requests.get(url, auth=auth)
            
            if not response.ok:
                print(f"Full response headers: {response.headers}")
                raise ValueError(
                    f"Bitbucket API error: {response.status_code} - {response.text}\n"
                    f"URL: {url}\n"
                    "Please check your Bitbucket credentials and workspace name"
                )
            
            try:
                data = response.json()
                all_repos.extend(data.get('values', []))
                
                # Get URL for next page
                url = data.get('next')
                
            except requests.exceptions.JSONDecodeError:
                print(f"Failed to decode response. Status code: {response.status_code}")
                print(f"Response text: {response.text}")
                break
        
        filtered_repos = [
            repo for repo in all_repos 
            if any(repo['name'].startswith(prefix) for prefix in BITBUCKET_ALLOWED_PREFIXES)
        ]
        
        # Apply visibility filter
        filtered_repos = self._filter_repos_by_visibility(filtered_repos, is_github=False)
        
        print(f"Total Bitbucket repos: {len(all_repos)}")
        print(f"Filtered Bitbucket repos: {len(filtered_repos)}")
        print("Filtered repo names:", [repo['name'] for repo in filtered_repos])
        
        return filtered_repos

    def process_repositories(self):
        """Main processing function"""
        index_content = "# Repository Documentation Index\n\n"
        
        # Process GitHub repositories
        index_content += self._process_github_repositories()
        
        # Process Bitbucket repositories
        index_content += self._process_bitbucket_repositories()
        
        # Save index file
        with open(self.output_dir / "index.md", "w", encoding="utf-8") as f:
            f.write(index_content)

    def _generate_llm_txt(self, repo_url: str, output_path: str):
        """Generate llm.txt file using gitingest directly from URL"""
        subprocess.run([
            "gitingest",
            repo_url,
            "--output",
            output_path
        ], check=True)

    def _process_github_repositories(self) -> str:
        """Process GitHub repositories and return index content"""
        content = "## GitHub Repositories\n\n"
        github_repos = self._get_github_repos()
        
        print(f"Found {len(github_repos)} GitHub repositories matching prefixes {GITHUB_ALLOWED_PREFIXES}")
        
        for repo in github_repos:
            repo_name = repo['name']
            print(f"Processing GitHub repo: {repo_name}")
            
            # Generate documentation
            output_dir = self.output_dir / "github" / repo_name
            output_dir.mkdir(parents=True, exist_ok=True)
            self._generate_llm_txt(repo['html_url'], str(output_dir / "llm.txt"))
            
            # Add to index
            relative_path = os.path.relpath(output_dir / "llm.txt", self.output_dir)
            content += f"### {repo_name}\n"
            content += f"- [Documentation]({relative_path})\n"
            content += f"- Repository: {repo['html_url']}\n"
            content += f"- Description: {repo.get('description', 'No description')}\n\n"
        
        return content

    def _process_bitbucket_repositories(self) -> str:
        """Process Bitbucket repositories and return index content"""
        content = "## Bitbucket Repositories\n\n"
        bitbucket_repos = self._get_bitbucket_repos()
        
        print(f"Found {len(bitbucket_repos)} Bitbucket repositories matching prefixes {BITBUCKET_ALLOWED_PREFIXES}")
        
        for repo in bitbucket_repos:
            repo_name = repo['name']
            print(f"Processing Bitbucket repo: {repo_name}")
            
            # Generate documentation
            output_dir = self.output_dir / "bitbucket" / repo_name
            output_dir.mkdir(parents=True, exist_ok=True)
            self._generate_llm_txt(repo['links']['html']['href'], str(output_dir / "llm.txt"))
            
            # Add to index
            relative_path = os.path.relpath(output_dir / "llm.txt", self.output_dir)
            content += f"### {repo_name}\n"
            content += f"- [Documentation]({relative_path})\n"
            content += f"- Repository: {repo['links']['html']['href']}\n"
            content += f"- Description: {repo.get('description', 'No description')}\n\n"
        
        return content


if __name__ == "__main__":
    processor = RepoProcessor()
    processor.process_repositories()