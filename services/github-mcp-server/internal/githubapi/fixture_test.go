package githubapi

import (
	"path/filepath"
	"testing"
)

func fixturePath(t *testing.T) string {
	t.Helper()
	return filepath.Join("..", "..", "fixtures", "demo.json")
}

func TestFixtureCommitAndPRCorrelation(t *testing.T) {
	client, err := NewFixtureClient(fixturePath(t))
	if err != nil {
		t.Fatal(err)
	}

	commit, err := client.GetCommit("aaaaaaaaaaaa")
	if err != nil {
		t.Fatal(err)
	}
	if len(commit.Files) != 1 {
		t.Fatalf("expected one changed file, got %d", len(commit.Files))
	}
	if commit.Files[0].Filename != "demo/kubernetes/base/payment.yaml" {
		t.Fatalf("unexpected file %s", commit.Files[0].Filename)
	}

	prs, err := client.FindPullRequestsForCommit(commit.SHA)
	if err != nil {
		t.Fatal(err)
	}
	if len(prs) != 1 || prs[0].Number != 42 {
		t.Fatalf("expected PR #42, got %#v", prs)
	}
}

func TestFixtureCompare(t *testing.T) {
	client, err := NewFixtureClient(fixturePath(t))
	if err != nil {
		t.Fatal(err)
	}
	comparison, err := client.CompareCommits("111111111111", "cccccccccccc")
	if err != nil {
		t.Fatal(err)
	}
	if comparison.TotalCommits != 1 {
		t.Fatalf("expected one commit, got %d", comparison.TotalCommits)
	}
	if len(comparison.Files) != 1 {
		t.Fatalf("expected one file, got %d", len(comparison.Files))
	}
}
