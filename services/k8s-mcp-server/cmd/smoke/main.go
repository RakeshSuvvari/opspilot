package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func main() {
	endpoint := flag.String("endpoint", "http://localhost:8080/mcp", "MCP Streamable HTTP endpoint")
	namespace := flag.String("namespace", "opspilot-demo", "Kubernetes namespace used for the smoke call")
	flag.Parse()

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	client := mcp.NewClient(&mcp.Implementation{Name: "opspilot-smoke", Version: "0.2.0"}, nil)
	session, err := client.Connect(ctx, &mcp.StreamableClientTransport{Endpoint: *endpoint}, nil)
	if err != nil {
		log.Fatalf("connect to MCP server: %v", err)
	}
	defer session.Close()

	tools, err := session.ListTools(ctx, nil)
	if err != nil {
		log.Fatalf("list MCP tools: %v", err)
	}

	fmt.Println("Available tools:")
	for _, tool := range tools.Tools {
		fmt.Printf("- %s\n", tool.Name)
	}

	result, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name: "k8s_list_pods",
		Arguments: map[string]any{
			"namespace": *namespace,
		},
	})
	if err != nil {
		log.Fatalf("call k8s_list_pods: %v", err)
	}
	if result.IsError {
		log.Fatalf("k8s_list_pods returned an MCP tool error")
	}

	fmt.Println("\nk8s_list_pods result:")
	if result.StructuredContent != nil {
		encoded, err := json.MarshalIndent(result.StructuredContent, "", "  ")
		if err != nil {
			log.Fatalf("format structured result: %v", err)
		}
		fmt.Println(string(encoded))
		return
	}

	for _, content := range result.Content {
		if text, ok := content.(*mcp.TextContent); ok {
			fmt.Println(text.Text)
		}
	}

	if len(result.Content) == 0 {
		fmt.Fprintln(os.Stderr, "tool returned no content")
	}
}
