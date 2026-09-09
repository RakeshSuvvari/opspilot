package githubapi

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

type LiveClient struct {
	httpClient *http.Client
	baseURL    string
	owner      string
	repository string
	token      string
}

func NewLiveClient(baseURL, owner, repository, token string) (*LiveClient, error) {
	if strings.TrimSpace(owner) == "" || strings.TrimSpace(repository) == "" {
		return nil, fmt.Errorf("OPSPILOT_GITHUB_OWNER and OPSPILOT_GITHUB_REPO are required in live mode")
	}
	return &LiveClient{
		httpClient: &http.Client{Timeout: 15 * time.Second},
		baseURL:    strings.TrimRight(baseURL, "/"),
		owner:      owner,
		repository: repository,
		token:      strings.TrimSpace(token),
	}, nil
}

func (c *LiveClient) Repository() Repository {
	return Repository{Owner: c.owner, Name: c.repository}
}

func (c *LiveClient) ListRecentCommits(limit int) ([]CommitSummary, error) {
	if limit <= 0 {
		limit = 10
	}
	if limit > 50 {
		limit = 50
	}
	var response []apiCommit
	endpoint := fmt.Sprintf("/repos/%s/%s/commits?per_page=%d", esc(c.owner), esc(c.repository), limit)
	if err := c.get(endpoint, &response); err != nil {
		return nil, err
	}
	results := make([]CommitSummary, 0, len(response))
	for _, commit := range response {
		results = append(results, commit.summary())
	}
	return results, nil
}

func (c *LiveClient) GetCommit(sha string) (CommitDetails, error) {
	var response apiCommit
	endpoint := fmt.Sprintf("/repos/%s/%s/commits/%s", esc(c.owner), esc(c.repository), esc(sha))
	if err := c.get(endpoint, &response); err != nil {
		return CommitDetails{}, err
	}
	return response.details(), nil
}

func (c *LiveClient) CompareCommits(base, head string) (CompareDetails, error) {
	var response apiCompare
	endpoint := fmt.Sprintf("/repos/%s/%s/compare/%s...%s", esc(c.owner), esc(c.repository), esc(base), esc(head))
	if err := c.get(endpoint, &response); err != nil {
		return CompareDetails{}, err
	}
	result := CompareDetails{
		BaseSHA:      response.BaseCommit.SHA,
		HeadSHA:      response.MergeBaseCommit.SHA,
		Status:       response.Status,
		AheadBy:      response.AheadBy,
		BehindBy:     response.BehindBy,
		TotalCommits: response.TotalCommits,
		Files:        normalizeFiles(response.Files),
		HTMLURL:      response.HTMLURL,
	}
	if response.Commits != nil && len(response.Commits) > 0 {
		result.HeadSHA = response.Commits[len(response.Commits)-1].SHA
	}
	for _, commit := range response.Commits {
		result.Commits = append(result.Commits, commit.summary())
	}
	return result, nil
}

func (c *LiveClient) FindPullRequestsForCommit(sha string) ([]PullRequestSummary, error) {
	var response []apiPullRequest
	endpoint := fmt.Sprintf("/repos/%s/%s/commits/%s/pulls", esc(c.owner), esc(c.repository), esc(sha))
	if err := c.get(endpoint, &response); err != nil {
		return nil, err
	}
	results := make([]PullRequestSummary, 0, len(response))
	for _, pr := range response {
		results = append(results, pr.summary())
	}
	return results, nil
}

func (c *LiveClient) GetPullRequest(number int) (PullRequestDetails, error) {
	var response apiPullRequest
	endpoint := fmt.Sprintf("/repos/%s/%s/pulls/%s", esc(c.owner), esc(c.repository), strconv.Itoa(number))
	if err := c.get(endpoint, &response); err != nil {
		return PullRequestDetails{}, err
	}
	return response.details(), nil
}

func (c *LiveClient) get(endpoint string, target any) error {
	request, err := http.NewRequest(http.MethodGet, c.baseURL+endpoint, nil)
	if err != nil {
		return err
	}
	request.Header.Set("Accept", "application/vnd.github+json")
	request.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	request.Header.Set("User-Agent", "OpsPilot-GitHub-MCP")
	if c.token != "" {
		request.Header.Set("Authorization", "Bearer "+c.token)
	}

	response, err := c.httpClient.Do(request)
	if err != nil {
		return fmt.Errorf("GitHub request %s: %w", endpoint, err)
	}
	defer response.Body.Close()

	if response.StatusCode < 200 || response.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(response.Body, 4096))
		return fmt.Errorf("GitHub API %s returned %s: %s", endpoint, response.Status, strings.TrimSpace(string(body)))
	}
	if err := json.NewDecoder(response.Body).Decode(target); err != nil {
		return fmt.Errorf("decode GitHub response %s: %w", endpoint, err)
	}
	return nil
}

func esc(value string) string { return url.PathEscape(value) }

type apiCommit struct {
	SHA     string `json:"sha"`
	HTMLURL string `json:"html_url"`
	Commit  struct {
		Message string `json:"message"`
		Author  struct {
			Name  string `json:"name"`
			Email string `json:"email"`
			Date  string `json:"date"`
		} `json:"author"`
	} `json:"commit"`
	Author *struct {
		Login string `json:"login"`
	} `json:"author"`
	Parents []struct {
		SHA string `json:"sha"`
	} `json:"parents"`
	Files []apiFile `json:"files"`
}

func (c apiCommit) summary() CommitSummary {
	author := Author{Name: c.Commit.Author.Name, Email: c.Commit.Author.Email}
	if c.Author != nil {
		author.Login = c.Author.Login
	}
	return CommitSummary{SHA: c.SHA, Message: c.Commit.Message, AuthoredAt: c.Commit.Author.Date, Author: author, HTMLURL: c.HTMLURL}
}

func (c apiCommit) details() CommitDetails {
	summary := c.summary()
	result := CommitDetails{
		SHA: summary.SHA, Message: summary.Message, AuthoredAt: summary.AuthoredAt,
		Author: summary.Author, HTMLURL: summary.HTMLURL, Files: normalizeFiles(c.Files),
	}
	for _, parent := range c.Parents {
		result.Parents = append(result.Parents, parent.SHA)
	}
	return result
}

type apiFile struct {
	Filename  string `json:"filename"`
	Status    string `json:"status"`
	Additions int    `json:"additions"`
	Deletions int    `json:"deletions"`
	Changes   int    `json:"changes"`
	Patch     string `json:"patch"`
}

func normalizeFiles(files []apiFile) []FileChange {
	result := make([]FileChange, 0, len(files))
	for _, file := range files {
		patch := file.Patch
		if len(patch) > 6000 {
			patch = patch[:6000] + "\n...<truncated>"
		}
		result = append(result, FileChange{Filename: file.Filename, Status: file.Status, Additions: file.Additions, Deletions: file.Deletions, Changes: file.Changes, Patch: patch})
	}
	return result
}

type apiCompare struct {
	Status          string      `json:"status"`
	AheadBy         int         `json:"ahead_by"`
	BehindBy        int         `json:"behind_by"`
	TotalCommits    int         `json:"total_commits"`
	HTMLURL         string      `json:"html_url"`
	BaseCommit      apiCommit   `json:"base_commit"`
	MergeBaseCommit apiCommit   `json:"merge_base_commit"`
	Commits         []apiCommit `json:"commits"`
	Files           []apiFile   `json:"files"`
}

type apiPullRequest struct {
	Number       int    `json:"number"`
	Title        string `json:"title"`
	State        string `json:"state"`
	Merged       bool   `json:"merged"`
	MergedAt     string `json:"merged_at"`
	Body         string `json:"body"`
	HTMLURL      string `json:"html_url"`
	Commits      int    `json:"commits"`
	Additions    int    `json:"additions"`
	Deletions    int    `json:"deletions"`
	ChangedFiles int    `json:"changed_files"`
	User         struct {
		Login string `json:"login"`
	} `json:"user"`
	Base struct {
		Ref string `json:"ref"`
	} `json:"base"`
	Head struct {
		Ref string `json:"ref"`
		SHA string `json:"sha"`
	} `json:"head"`
}

func (p apiPullRequest) summary() PullRequestSummary {
	return PullRequestSummary{Number: p.Number, Title: p.Title, State: p.State, Merged: p.Merged, MergedAt: p.MergedAt, BaseRef: p.Base.Ref, HeadRef: p.Head.Ref, HeadSHA: p.Head.SHA, Author: p.User.Login, Body: p.Body, HTMLURL: p.HTMLURL}
}

func (p apiPullRequest) details() PullRequestDetails {
	summary := p.summary()
	return PullRequestDetails{
		Number: summary.Number, Title: summary.Title, State: summary.State, Merged: summary.Merged,
		MergedAt: summary.MergedAt, BaseRef: summary.BaseRef, HeadRef: summary.HeadRef, HeadSHA: summary.HeadSHA,
		Author: summary.Author, Body: summary.Body, HTMLURL: summary.HTMLURL, Commits: p.Commits,
		Additions: p.Additions, Deletions: p.Deletions, ChangedFiles: p.ChangedFiles,
	}
}
