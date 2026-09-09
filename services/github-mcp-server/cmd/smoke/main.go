package main

import (
	"context"
	"flag"
	"fmt"
	"log"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func main() {
	endpoint := flag.String("endpoint", "http://localhost:8090/mcp", "GitHub MCP endpoint")
	flag.Parse()

	ctx := context.Background()
	client := mcp.NewClient(&mcp.Implementation{Name: "opspilot-github-smoke", Version: "0.6.0"}, nil)
	session, err := client.Connect(ctx, &mcp.StreamableClientTransport{Endpoint: *endpoint}, nil)
	if err != nil {
		log.Fatal(err)
	}
	defer session.Close()

	tools, err := session.ListTools(ctx, nil)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("Available GitHub MCP tools:")
	for _, tool := range tools.Tools {
		fmt.Printf("- %s\n", tool.Name)
	}

	result, err := session.CallTool(ctx, &mcp.CallToolParams{Name: "github_list_recent_commits", Arguments: map[string]any{"limit": 5}})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("\nRecent commits:\n%v\n", result.StructuredContent)
}
