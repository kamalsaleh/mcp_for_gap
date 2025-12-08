# MCP for GAP

Model Context Protocol (MCP) server implementation for GAP (Groups, Algorithms, Programming) packages.

## Overview

This project provides a unified MCP server that exposes GAP package functions as tools that can be called by MCP clients (like Claude Desktop, Cherry-Studio, Cline, etc.).

## Features

- **Unified Server**: Single MCP server with tools from specified GAP packages
- **Dynamic Tool Loading**: Automatically extracts tools from GAP package documented using AutoDoc
- **Package-Specific Configuration**: Customize tool filtering per package via `mcp_for_gap/files/config.yml`
- **Namespaced Tools**: Tools from different packages are prefixed to avoid naming conflicts

## Architecture

```
config.yml → extract_tools.py → JSON files → mcp_server.py → MCP Clients
                                ↓              ↓
                          path-to/mcp_for_gap/files/packages/   GAP Session
                          ├── CAP.json
                          ├── LinearAlgebraForCAP.json
                          └── ModulePresentationsForCAP.json
```

## Installation

1. Make sure GAP is installed and available in your PATH
2. Install Python mcp package:

   ```bash
   pip install mcp
   ```

## Configuration

### 1. Configure GAP Packages (config.yml)

Specify in the file `config.yml` which GAP packages to export and which tools to include/exclude:

```yaml
packages:
  - name: LinearAlgebraForCAP
    tools:
      - MatrixCategory
      - VectorSpaceObject
      - VectorSpaceMorphism
  - name: ModulePresentationsForCAP
    tools:
      - all
    exclude_tools_with_subwords:
      - INSTALL

extract_mcp_schema_for:
  - LinearAlgebraForCAP
  - ModulePresentationsForCAP
```

### 2. Extract Tools

Run the extraction script to generate JSON tool definitions:

```bash
python3 extract_tools.py
```

This will create JSON files in `mcp_for_gap/files/packages/` directory.

### 3. Configure MCP Client

Add the unified server to your MCP client configuration. The server will automatically load tools from all GAP packages.

#### For Claude Desktop

Edit your Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Add the following configuration:

```json
 {
  "mcpServers": {
    "gap": {
      "command": "python3",
      "args": [
        "/absolute/path/to/mcp_for_gap/mcp_server.py"
      ]
    }
  }
}
```

#### For Other MCP Clients

Use the same command and arguments pattern. The server communicates via stdio and works with any MCP-compatible client.

**Important**: Replace `/absolute/path/to/mcp_for_gap/mcp_server.py` with the actual absolute path to your cloned directory.

## Usage

### Running the Server

Simply run the server (it will load all packages automatically):

```bash
python3 mcp_server.py
```

The server will:

- Load tools from all JSON files in `mcp_for_gap/files/packages`
- Create a GAP session
- Start the MCP server listening on stdio

### Using with MCP Clients

Once configured, the tools will be available in your MCP client. Tool names are prefixed with package abbreviations to avoid conflicts. The prefix is formed from capital letters in the package name:

- **ModulePresentationsForCAP** → `MPFCAP_` prefix
- **LinearAlgebraForCAP** → `LAFCAP_` prefix
- **CAP** → `CAP_` prefix

**Example tool names:**

* Call `GAP_EvalCode` to execute arbitrary GAP code
* Call `MPFCAP_FreeLeftPresentation` to create a free left presentation
* Call `MPFCAP_AsLeftPresentation` to convert a matrix to a left presentation
* Call `LAFCAP_Dimension` to get the dimension of a vector space object

**Example Usage in Claude Desktop:**

```
Use the GAP_EvalCode tool to compute the symmetric group S4:
code: "SymmetricGroup(4);"
```

## File Structure

- `mcp_server.py` - MCP server that loads all packages and shares one GAP session
- `extract_tools.py` - Extracts tool definitions from GAP package documentation
- `gapwrapper.py` - Python wrapper for GAP process
- `files/config.yml` - YAML configuration for packages and tool filtering.
- `files/GAP.json` -  Json file to run arbitrary GAP code.
- `files/packages/` - User-extracted JSON tool definitions

## How It Works

1. **Tool Extraction**: `extract_tools.py` parses GAP package XML documentation and extracts function signatures, descriptions, and parameter types.
2. **Tool Filtering**: Each package can have custom exclusion rules to filter out internal or utility functions.
3. **Unified Server**: `mcp_server.py` creates a single MCP server that loads tools from all packages specified in `mcp_for_gap/files/config.yml`, prefixing them with package abbreviations (formed from capital letters in package names) to avoid naming conflicts.
4. **Shared GAP Session**: All tools use the same GAP process instance, making it efficient and allowing state to be shared across function calls.
5. **GAP Execution**: When a tool is called, the server constructs a GAP command using the original function name and executes it via the shared `gapwrapper`, returning the result to the client.

## Development

### Adding New Packages

1. Add the package to `mcp_for_gap/files/config.yml`:

   ```yaml
   - name: YourPackage
     tools:
       - all
     exclude_tools_with_subwords:
       - InternalFunction
   ```
2. Run the extraction:

   ```bash
   python3 extract_tools.py
   ```
3. Restart your MCP client - the new tools will be automatically loaded

Test GAP integration directly:

```python
from gapwrapper import GAP
gap = GAP()
print(gap("SymmetricGroup(4);"))
```

Test tool loading:

```python
from mcp_server import load_all_tools
tools = load_all_tools()
print(f"Loaded {len(tools)} tools")
```

## License

ISC

## Contributing

Contributions welcome! Please feel free to submit pull requests or open issues.
