import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict
import requests
from git import Repo
import yaml


class RepoProcessor:
    def __init__(self, config_path: str = "repo_config.yml"):
        """
        Initialize with configuration file containing API tokens and repo lists
        """
        self.config = self._load_config(config_path)
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path("./docs_collection")
        self.output_dir.mkdir(exist_ok=True)

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _get_github_repos(self) -> List[Dict]:
        """Fetch list of repositories from GitHub"""
        headers = {
            'Authorization': f"token {self.config['github_token']}",
            'Accept': 'application/vnd.github.v3+json'
        }
        response = requests.get(
            f"https://api.github.com/orgs/{self.config['github_org']}/repos",
            headers=headers
        )
        return response.json()

    def _get_bitbucket_repos(self) -> List[Dict]:
        """Fetch list of repositories from Bitbucket"""
        auth = (self.config['bitbucket_username'], self.config['bitbucket_token'])
        response = requests.get(
            f"https://api.bitbucket.org/2.0/repositories/{self.config['bitbucket_workspace']}",
            auth=auth
        )
        return response.json()['values']

    def _clone_repo(self, clone_url: str, repo_name: str) -> str:
        """Clone repository to temporary directory"""
        repo_path = os.path.join(self.temp_dir, repo_name)
        Repo.clone_from(clone_url, repo_path)
        return repo_path

    def _generate_llm_txt(self, repo_path: str, output_path: str):
        """Generate llm.txt file using gitingest"""
        subprocess.run([
            "gitingest",
            repo_path,
            "--output",
            output_path
        ], check=True)

    def process_repositories(self):
        """Main processing function"""
        index_content = "# Repository Documentation Index\n\n"

        # Process GitHub repositories
        github_repos = self._get_github_repos()
        index_content += "## GitHub Repositories\n\n"
        for repo in github_repos:
            repo_name = repo['name']
            clone_url = repo['clone_url']
            output_dir = self.output_dir / "github" / repo_name
            output_dir.mkdir(parents=True, exist_ok=True)

            # Clone and process
            repo_path = self._clone_repo(clone_url, repo_name)
            self._generate_llm_txt(repo_path, str(output_dir / "llm.txt"))

            # Add to index
            relative_path = os.path.relpath(output_dir / "llm.txt", self.output_dir)
            index_content += f"### {repo_name}\n"
            index_content += f"- [Documentation]({relative_path})\n"
            index_content += f"- Original: {repo['html_url']}\n\n"

        # Process Bitbucket repositories
        bitbucket_repos = self._get_bitbucket_repos()
        index_content += "## Bitbucket Repositories\n\n"
        for repo in bitbucket_repos:
            repo_name = repo['name']
            clone_url = repo['links']['clone'][0]['href']  # HTTPS clone URL
            output_dir = self.output_dir / "bitbucket" / repo_name
            output_dir.mkdir(parents=True, exist_ok=True)

            # Clone and process
            repo_path = self._clone_repo(clone_url, repo_name)
            self._generate_llm_txt(repo_path, str(output_dir / "llm.txt"))

            # Add to index
            relative_path = os.path.relpath(output_dir / "llm.txt", self.output_dir)
            index_content += f"### {repo_name}\n"
            index_content += f"- [Documentation]({relative_path})\n"
            index_content += f"- Original: {repo['links']['html']['href']}\n\n"

        # Save index file
        with open(self.output_dir / "index.md", "w", encoding="utf-8") as f:
            f.write(index_content)


if __name__ == "__main__":
    processor = RepoProcessor()
    processor.process_repositories()