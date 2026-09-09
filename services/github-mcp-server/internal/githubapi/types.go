package githubapi

type Repository struct {
	Owner         string `json:"owner"`
	Name          string `json:"name"`
	DefaultBranch string `json:"default_branch"`
}

type Author struct {
	Name  string `json:"name,omitempty"`
	Login string `json:"login,omitempty"`
	Email string `json:"email,omitempty"`
}

type FileChange struct {
	Filename  string `json:"filename"`
	Status    string `json:"status"`
	Additions int    `json:"additions"`
	Deletions int    `json:"deletions"`
	Changes   int    `json:"changes"`
	Patch     string `json:"patch,omitempty"`
}

type CommitSummary struct {
	SHA        string `json:"sha"`
	Message    string `json:"message"`
	AuthoredAt string `json:"authored_at,omitempty"`
	Author     Author `json:"author"`
	HTMLURL    string `json:"html_url,omitempty"`
}

type CommitDetails struct {
	SHA        string       `json:"sha"`
	Message    string       `json:"message"`
	AuthoredAt string       `json:"authored_at,omitempty"`
	Author     Author       `json:"author"`
	HTMLURL    string       `json:"html_url,omitempty"`
	Parents    []string     `json:"parents,omitempty"`
	Files      []FileChange `json:"files,omitempty"`
}

func (c CommitDetails) Summary() CommitSummary {
	return CommitSummary{SHA: c.SHA, Message: c.Message, AuthoredAt: c.AuthoredAt, Author: c.Author, HTMLURL: c.HTMLURL}
}

type CompareDetails struct {
	BaseSHA      string          `json:"base_sha"`
	HeadSHA      string          `json:"head_sha"`
	Status       string          `json:"status"`
	AheadBy      int             `json:"ahead_by"`
	BehindBy     int             `json:"behind_by"`
	TotalCommits int             `json:"total_commits"`
	Commits      []CommitSummary `json:"commits,omitempty"`
	Files        []FileChange    `json:"files,omitempty"`
	HTMLURL      string          `json:"html_url,omitempty"`
}

type PullRequestSummary struct {
	Number   int    `json:"number"`
	Title    string `json:"title"`
	State    string `json:"state"`
	Merged   bool   `json:"merged"`
	MergedAt string `json:"merged_at,omitempty"`
	BaseRef  string `json:"base_ref,omitempty"`
	HeadRef  string `json:"head_ref,omitempty"`
	HeadSHA  string `json:"head_sha,omitempty"`
	Author   string `json:"author,omitempty"`
	Body     string `json:"body,omitempty"`
	HTMLURL  string `json:"html_url,omitempty"`
}

type PullRequestDetails struct {
	Number       int    `json:"number"`
	Title        string `json:"title"`
	State        string `json:"state"`
	Merged       bool   `json:"merged"`
	MergedAt     string `json:"merged_at,omitempty"`
	BaseRef      string `json:"base_ref,omitempty"`
	HeadRef      string `json:"head_ref,omitempty"`
	HeadSHA      string `json:"head_sha,omitempty"`
	Author       string `json:"author,omitempty"`
	Body         string `json:"body,omitempty"`
	HTMLURL      string `json:"html_url,omitempty"`
	Commits      int    `json:"commits"`
	Additions    int    `json:"additions"`
	Deletions    int    `json:"deletions"`
	ChangedFiles int    `json:"changed_files"`
}

func (p PullRequestDetails) Summary() PullRequestSummary {
	return PullRequestSummary{
		Number: p.Number, Title: p.Title, State: p.State, Merged: p.Merged, MergedAt: p.MergedAt,
		BaseRef: p.BaseRef, HeadRef: p.HeadRef, HeadSHA: p.HeadSHA, Author: p.Author, Body: p.Body, HTMLURL: p.HTMLURL,
	}
}

type Client interface {
	Repository() Repository
	ListRecentCommits(limit int) ([]CommitSummary, error)
	GetCommit(sha string) (CommitDetails, error)
	CompareCommits(base, head string) (CompareDetails, error)
	FindPullRequestsForCommit(sha string) ([]PullRequestSummary, error)
	GetPullRequest(number int) (PullRequestDetails, error)
}
