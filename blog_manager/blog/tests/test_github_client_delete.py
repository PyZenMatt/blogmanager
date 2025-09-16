import pytest
from unittest.mock import MagicMock, patch


@patch("blog.github_client.Github")
def test_delete_file_happy_path(GithubMock):
    # Setup repository and return value for delete_file
    gh_instance = GithubMock.return_value
    repo = gh_instance.get_repo.return_value

    contents = MagicMock()
    contents.sha = "oldsha"
    repo.get_contents.return_value = contents

    # Simulate delete_file returning a dict with commit
    fake_commit = MagicMock()
    fake_commit.sha = "commitsha123"
    repo.delete_file.return_value = {"commit": fake_commit}

    from blog.github_client import GitHubClient

    client = GitHubClient(token="fake")
    res = client.delete_file("owner", "repo", "path/to/file.md", branch="main", message="del")

    assert res["status"] == "deleted"
    assert res["commit_sha"] == "commitsha123"


@patch("blog.github_client.Github")
def test_delete_file_already_absent(GithubMock):
    gh_instance = GithubMock.return_value
    repo = gh_instance.get_repo.return_value

    from github import GithubException

    # Simulate get_contents raising 404
    err = GithubException(404, "Not Found")
    repo.get_contents.side_effect = err

    from blog.github_client import GitHubClient

    client = GitHubClient(token="fake")
    res = client.delete_file("owner", "repo", "path/to/missing.md", branch="main", message="del")

    assert res["status"] == "already_absent"
    assert res["commit_sha"] is None


@patch("blog.github_client.Github")
def test_delete_file_permission_error_propagates(GithubMock):
    gh_instance = GithubMock.return_value
    repo = gh_instance.get_repo.return_value

    from github import GithubException

    # Simulate get_contents raising 403
    err = GithubException(403, "Forbidden")
    repo.get_contents.side_effect = err

    from blog.github_client import GitHubClient

    client = GitHubClient(token="fake")
    with pytest.raises(GithubException):
        client.delete_file("owner", "repo", "path/to/file.md", branch="main", message="del")


@patch("blog.github_client.Github")
def test_service_wrapper_records_exportjob(GithubMock):
    gh_instance = GithubMock.return_value
    repo = gh_instance.get_repo.return_value

    contents = MagicMock()
    contents.sha = "oldsha"
    repo.get_contents.return_value = contents

    fake_commit = MagicMock()
    fake_commit.sha = "commitsha123"
    repo.delete_file.return_value = {"commit": fake_commit}

    from blog.services.github_ops import delete_post_from_repo

    class DummyPost:
        pk = 1
        repo_owner = "owner"
        repo_name = "repo"
        repo_path = "path/to/file.md"
        repo_branch = "main"

    post = DummyPost()

    with patch("blog.models.ExportJob") as EJMock:
        res = delete_post_from_repo(post, message="del")
        # ExportJob.objects.create should be called
        assert EJMock.objects.create.called
        assert res["status"] == "deleted"

