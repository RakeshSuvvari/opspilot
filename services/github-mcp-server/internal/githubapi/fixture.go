package githubapi

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"time"
)

type fixtureData struct {
	Repository   Repository           `json:"repository"`
	Commits      []CommitDetails      `json:"commits"`
	PullRequests []fixturePullRequest `json:"pull_requests"`
}

type fixturePullRequest struct {
	PullRequestDetails
	CommitSHAs []string `json:"commit_shas"`
}

type FixtureClient struct {
	data fixtureData
}

func NewFixtureClient(path string) (*FixtureClient, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read GitHub fixture %s: %w", path, err)
	}
	var data fixtureData
	if err := json.Unmarshal(raw, &data); err != nil {
		return nil, fmt.Errorf("parse GitHub fixture %s: %w", path, err)
	}
	if data.Repository.Owner == "" || data.Repository.Name == "" {
		return nil, fmt.Errorf("GitHub fixture repository owner/name are required")
	}
	return &FixtureClient{data: data}, nil
}

func (c *FixtureClient) Repository() Repository { return c.data.Repository }

func (c *FixtureClient) ListRecentCommits(limit int) ([]CommitSummary, error) {
	if limit <= 0 {
		limit = 10
	}
	if limit > 50 {
		limit = 50
	}
	commits := make([]CommitSummary, 0, len(c.data.Commits))
	for _, commit := range c.data.Commits {
		commits = append(commits, commit.Summary())
	}
	sort.SliceStable(commits, func(i, j int) bool {
		left, _ := time.Parse(time.RFC3339, commits[i].AuthoredAt)
		right, _ := time.Parse(time.RFC3339, commits[j].AuthoredAt)
		return left.After(right)
	})
	if len(commits) > limit {
		commits = commits[:limit]
	}
	return commits, nil
}

func (c *FixtureClient) GetCommit(sha string) (CommitDetails, error) {
	for _, commit := range c.data.Commits {
		if matchesSHA(commit.SHA, sha) {
			return commit, nil
		}
	}
	return CommitDetails{}, fmt.Errorf("fixture commit %q not found", sha)
}

func (c *FixtureClient) CompareCommits(base, head string) (CompareDetails, error) {
	headCommit, err := c.GetCommit(head)
	if err != nil {
		return CompareDetails{}, err
	}
	baseCommit, err := c.GetCommit(base)
	if err != nil {
		return CompareDetails{}, err
	}

	commits := []CommitSummary{headCommit.Summary()}
	return CompareDetails{
		BaseSHA:      baseCommit.SHA,
		HeadSHA:      headCommit.SHA,
		Status:       "ahead",
		AheadBy:      1,
		BehindBy:     0,
		TotalCommits: 1,
		Commits:      commits,
		Files:        headCommit.Files,
		HTMLURL:      fmt.Sprintf("https://github.com/%s/%s/compare/%s...%s", c.data.Repository.Owner, c.data.Repository.Name, baseCommit.SHA, headCommit.SHA),
	}, nil
}

func (c *FixtureClient) FindPullRequestsForCommit(sha string) ([]PullRequestSummary, error) {
	var results []PullRequestSummary
	for _, pr := range c.data.PullRequests {
		for _, commitSHA := range pr.CommitSHAs {
			if matchesSHA(commitSHA, sha) {
				results = append(results, pr.Summary())
				break
			}
		}
	}
	return results, nil
}

func (c *FixtureClient) GetPullRequest(number int) (PullRequestDetails, error) {
	for _, pr := range c.data.PullRequests {
		if pr.Number == number {
			return pr.PullRequestDetails, nil
		}
	}
	return PullRequestDetails{}, fmt.Errorf("fixture pull request #%d not found", number)
}

func matchesSHA(full, requested string) bool {
	full = strings.TrimSpace(full)
	requested = strings.TrimSpace(requested)
	return full == requested || (requested != "" && strings.HasPrefix(full, requested))
}
