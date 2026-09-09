package tools

import (
	"context"
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/opspilot/opspilot/services/github-mcp-server/internal/githubapi"
)

type Server struct{ client githubapi.Client }

func New(client githubapi.Client) *Server { return &Server{client: client} }

func (s *Server) Register(server *mcp.Server) {
	mcp.AddTool(server, &mcp.Tool{Name: "github_list_recent_commits", Description: "List recent commits in the configured repository. Use when deployment provenance is unavailable or to inspect recent change history."}, s.listRecentCommits)
	mcp.AddTool(server, &mcp.Tool{Name: "github_get_commit", Description: "Get one commit with normalized changed files and a bounded patch. Use a deployment revision/SHA from Kubernetes when available."}, s.getCommit)
	mcp.AddTool(server, &mcp.Tool{Name: "github_compare_commits", Description: "Compare the previous deployed revision to the current revision and return changed files/patches. Preferred for determining exactly what changed in a rollout."}, s.compareCommits)
	mcp.AddTool(server, &mcp.Tool{Name: "github_find_pull_requests_for_commit", Description: "Find pull requests associated with a commit SHA so a deployment change can be linked to review context."}, s.findPullRequestsForCommit)
	mcp.AddTool(server, &mcp.Tool{Name: "github_get_pull_request", Description: "Get pull-request title, body, author, merge state, head SHA, and change statistics."}, s.getPullRequest)
}

type repositoryContext struct {
	Owner      string `json:"owner"`
	Repository string `json:"repository"`
}

type listRecentCommitsInput struct {
	Limit int `json:"limit,omitempty" jsonschema:"Maximum commits to return. Defaults to 10 and is capped at 50."`
}
type listRecentCommitsOutput struct {
	Repository repositoryContext         `json:"repository"`
	Count      int                       `json:"count"`
	Commits    []githubapi.CommitSummary `json:"commits"`
}

func (s *Server) listRecentCommits(_ context.Context, _ *mcp.CallToolRequest, input listRecentCommitsInput) (*mcp.CallToolResult, listRecentCommitsOutput, error) {
	commits, err := s.client.ListRecentCommits(input.Limit)
	if err != nil {
		return nil, listRecentCommitsOutput{}, err
	}
	repo := s.client.Repository()
	return nil, listRecentCommitsOutput{Repository: repositoryContext{Owner: repo.Owner, Repository: repo.Name}, Count: len(commits), Commits: commits}, nil
}

type getCommitInput struct {
	SHA string `json:"sha" jsonschema:"Commit SHA or unambiguous prefix from deployment provenance."`
}

func (s *Server) getCommit(_ context.Context, _ *mcp.CallToolRequest, input getCommitInput) (*mcp.CallToolResult, githubapi.CommitDetails, error) {
	if input.SHA == "" {
		return nil, githubapi.CommitDetails{}, fmt.Errorf("sha is required")
	}
	result, err := s.client.GetCommit(input.SHA)
	return nil, result, err
}

type compareCommitsInput struct {
	Base string `json:"base" jsonschema:"Previous deployed commit SHA/ref."`
	Head string `json:"head" jsonschema:"Current deployed commit SHA/ref."`
}

func (s *Server) compareCommits(_ context.Context, _ *mcp.CallToolRequest, input compareCommitsInput) (*mcp.CallToolResult, githubapi.CompareDetails, error) {
	if input.Base == "" || input.Head == "" {
		return nil, githubapi.CompareDetails{}, fmt.Errorf("base and head are required")
	}
	result, err := s.client.CompareCommits(input.Base, input.Head)
	return nil, result, err
}

type findPRsInput struct {
	SHA string `json:"sha" jsonschema:"Commit SHA whose associated pull requests should be returned."`
}
type findPRsOutput struct {
	Count        int                            `json:"count"`
	PullRequests []githubapi.PullRequestSummary `json:"pull_requests"`
}

func (s *Server) findPullRequestsForCommit(_ context.Context, _ *mcp.CallToolRequest, input findPRsInput) (*mcp.CallToolResult, findPRsOutput, error) {
	if input.SHA == "" {
		return nil, findPRsOutput{}, fmt.Errorf("sha is required")
	}
	prs, err := s.client.FindPullRequestsForCommit(input.SHA)
	if err != nil {
		return nil, findPRsOutput{}, err
	}
	return nil, findPRsOutput{Count: len(prs), PullRequests: prs}, nil
}

type getPullRequestInput struct {
	Number int `json:"number" jsonschema:"Pull request number."`
}

func (s *Server) getPullRequest(_ context.Context, _ *mcp.CallToolRequest, input getPullRequestInput) (*mcp.CallToolResult, githubapi.PullRequestDetails, error) {
	if input.Number <= 0 {
		return nil, githubapi.PullRequestDetails{}, fmt.Errorf("number must be positive")
	}
	result, err := s.client.GetPullRequest(input.Number)
	return nil, result, err
}
