#!/usr/bin/env python3
"""
MCP Server for GAP Package Documentation
Creates a single MCP server that exposes tools from all GAP packages,
sharing one GAP session for efficiency.
"""

import argparse
import json
import asyncio
import os
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from gapwrapper import GAP
from extract_tools import load_gap_config, get_packages_list
from pathlib import Path

# Single shared GAP instance for all packages
gap = GAP()

def gap_mcp_server_config():
  current_dir = os.path.dirname(os.path.abspath(__file__))
  print("Add the following to the \"mcpServers\" section of your client config.json:")
  print()
  print(
      '    "gap": {\n'
      '        "command": "python",\n'
      '        "args": [\n'
      f'            "{current_dir}/mcp_server.py"\n'
      "        ]\n"
      "    }\n"
  )
  
# List all mcp json files at ~/.gap/mcp_tools/
def list_mcp_json_files(packages):
    """List the needed MCP JSON files in the ~/.gap/mcp_tools/ directory."""
    
    json_files = [
      Path(__file__).parent / "files" / "GAP.json",
    ]
    
    search_dir = Path(__file__).parent.resolve() / "files" / "packages"
    
    # look for json files in these directories whose names contain package names
    if search_dir.exists() and search_dir.is_dir():
        for pkg in packages:
            pkg_json = search_dir / f"{pkg}.json"
            if pkg_json.exists() and pkg_json.is_file():
                json_files.append(pkg_json)
    
    return json_files

def load_tools_from_json_file(json_file: Path):
    """Load tool definitions from a single JSON file."""
    with open(json_file, 'r') as f:
        data = json.load(f)
        return data.get('tools', [])

def load_all_tools(packages):
    """Load tools from all JSON files with package prefixes."""
    all_tools = {}
    json_files = list_mcp_json_files(packages)
    
    for json_file in json_files:
        package_name = json_file.stem
        tools = load_tools_from_json_file(json_file)
        
        # extract prefix (take capital letters from package name)
        prefix = ("".join([c for c in package_name if c.isupper()]) or package_name)[:6]
        
        # Prefix tool names with package name to avoid conflicts
        for tool in tools:
            prefixed_name = f"{prefix}_{tool['name'][:50]}"
            all_tools[prefixed_name] = {
                **tool,
                'original_name': tool['name'],
                'package': package_name,
                'name': prefixed_name
            }
    
    return all_tools

def create_unified_server(packages):
    """Create a single MCP server with all GAP package tools."""
    app = Server("gap")
    
    # Load all tools at startup
    all_tools = load_all_tools(packages)
    
    @app.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available GAP package tools from all packages."""
        tools = []
        for tool_data in all_tools.values():
            tools.append(Tool(
                name=tool_data['name'],
                description=tool_data['description'],
                inputSchema=tool_data['inputSchema']
            ))
        return tools

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """
        Execute GAP functions using the shared gapwrapper instance.
        
        Constructs a GAP function call from the tool name and arguments,
        executes it via gap(), and returns the result.
        """
        if name == "GAP_Restart":
            try:
              gap.restart()
              return [TextContent(
                      type="text",
                      text="GAP session restarted successfully."
                    )]
            except Exception as e:
              raise Exception(f"Failed to restart GAP session: {e}")
        
        elif name == "GAP_EvalCode":
            code = arguments.get("code", "")
            
        else:
            # Find the tool definition
            tool_def = all_tools.get(name)
                  
            if not tool_def:
                raise Exception(f"Tool '{name}' not found.")
            
            # Build the GAP function call using the original function name
            original_name = tool_def['original_name']
            
            # Extract argument values in the order they appear in the schema
            variable_name = arguments.get("variable_name", "")
            required_args = tool_def['inputSchema'].get('required', [])
            arg_values = []
            
            for arg_name in required_args:
                if arg_name in arguments:
                    arg_values.append(arguments[arg_name])
                else:
                    raise Exception(f"Missing required argument: {arg_name}")
            
            # Construct the GAP command
            args_str = ", ".join(arg_values)
            
            code = f"{original_name}({args_str});"
            
            if variable_name:
                code = f"{variable_name} := {code}"
        
        # Execute the GAP command using the shared GAP instance
        return [TextContent(
                  type="text",
                  text=gap(code)
                )]

    @app.list_resources()
    async def list_resources():
        """List available resources (documentation)."""
        return []

    @app.read_resource()
    async def read_resource(uri: str):
        """Read resource content."""
        return f"{uri} content not implemented."
    
    return app

async def gap_mcp_server(packages):
    """Main entry point for the MCP server."""
    # Create the unified server with all packages
    app = create_unified_server(packages)
    
    # Test GAP connection (silently)
    try:
        gap("1+1;")
    except Exception as e:
        print(f"Error initializing GAP: {e}", file=sys.stderr)
        return
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
              )

def run_mcp_server(packages):
    """Run the MCP server."""
    asyncio.run(gap_mcp_server(packages))

if __name__ == "__main__":
    
    current_dir = Path(__file__).parent.resolve()
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument(
      "config_path",
      nargs="?",
      type=str,
      default=str(current_dir / "files/config.yml"),
    )
    args = parser.parse_args()
    
    gap_config_path = args.config_path
    gap_config = load_gap_config(gap_config_path)
    packages = ["GAP"] + get_packages_list(gap_config)
    
    run_mcp_server(packages)