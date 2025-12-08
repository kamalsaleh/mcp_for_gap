from importlib.resources import path
import xml.etree.ElementTree as ET
from pathlib import Path
import json
from typing import List, Dict, Any
import re
import yaml
from gapwrapper import GAP
import argparse

gap = GAP()

# extract the list of gap packages from config.yml
def load_gap_config(config_file: str) -> Dict[str, Any]:
    """Load GAP package configuration from YAML file."""
    config_path = Path(config_file).expanduser()
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file '{config_file}' not found. See README for setup instructions.")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config

def get_packages_list(config: Dict[str, Any]) -> List[str]:
    """Extract list of package names from config."""
    packages_names = config.get('extract_mcp_schema_for', ["all"])
    if packages_names == ["all"]:
      packages = config.get('packages', [])
      return [pkg['name'] for pkg in packages]
    else:
      return packages_names

def tools_to_extract_list(config: Dict[str, Any], package_name: str) -> List[str]:
    """Get the tools list for a specific package."""
    packages = config.get('packages', [])
    for pkg in packages:
        if pkg['name'] == package_name:
            return pkg.get('tools', ["all"])

def exclude_subwords_list(config: Dict[str, Any], package_name: str) -> List[str]:
    """Get the exclude_tools_with_subwords list for a specific package."""
    packages = config.get('packages', [])
    for pkg in packages:
        if pkg['name'] == package_name:
            return pkg.get('exclude_tools_with_subwords', [])
    return []

def preprocess_xml(xml_file: str) -> str:
    """Read XML file and handle entities."""
    with open(xml_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace common entities with their text equivalents or remove them
    # You can expand this dictionary based on what entities you encounter
    entities = {
        '&GAP;': 'GAP',
        '&CAP;': 'CAP',
        '&mathbf;': '',
        '&nbsp;': ' ',
        '&lt;': '<',
        '&gt;': '>',
        '&amp;': '&',
        '&quot;': '"',
        '&apos;': "'"
    }
    
    for entity, replacement in entities.items():
        content = content.replace(entity, replacement)
    
    # Remove any remaining undefined entities (optional, safer approach)
    # This regex finds &...; patterns
    content = re.sub(r'&[a-zA-Z]+;', '', content)
    
    # Turn <#X Y> into harmless comments
    content = re.sub(r'<#.*?>', '<!-- Commented out -->', content)
    
    return content


def extract_text(element):
    """Recursively extract all text from an XML element."""
    if element is None:
        return ""
    
    text = element.text or ''
    for child in element:
        text += extract_text(child)
        text += child.tail or ''
    return text.strip()

def sanity_check_tool(tool_name: str, tools: List[str], exclude_subwords: List[str]) -> bool:
  """Perform sanity checks on tool names."""
  
  if tools != ["all"] and tool_name not in tools:
    print(f"  - \033[93mSkipping tool '{tool_name}': not in the specified tools list of the package.\033[0m")
    return False
  
  # Check against package-specific exclude subwords
  for subword in exclude_subwords:
    if subword in tool_name:
      print(f"  - \033[93mSkipping tool '{tool_name}': contains excluded subword '{subword}'.\033[0m")
      return False
  
  # Make sure tool name is only alphanumeric and underscores
  if not re.match(r'^[A-Za-z0-9_]+$', tool_name):
    print(f"  - \033[93mSkipping tool '{tool_name}': contains invalid characters (only alphanumeric and underscores allowed).\033[0m")
    return False
  
  print(f"  - \033[92mIncluding tool '{tool_name}'.\033[0m")
  return True

def parse_mansection(mansection, chapter_name: str, section_name: str, package_name: str, tools: List[str], exclude_subwords: List[str]) -> List[Dict[str, Any]]:
    """Parse a ManSection element and extract function/method information."""
    functions = []
    
    # ManSection can contain multiple function definitions
    # Look for Attr, Oper, Func, Prop tags
    function_tags = mansection.findall('.//Attr') + \
                   mansection.findall('.//Oper') + \
                   mansection.findall('.//Func') + \
                   mansection.findall('.//Prop')
    
    # Get the description (shared by all functions in this ManSection)
    description_elem = mansection.find('.//Description')
    description = extract_text(description_elem) if description_elem is not None else ""
    
    # Get the Returns element (shared by all functions in this ManSection)
    returns_elem = mansection.find('.//Returns')
    returns = extract_text(returns_elem) if returns_elem is not None else ""
    
    for func_elem in function_tags:
        func_type = func_elem.tag  # Attr, Oper, Func, or Prop
        func_name = func_elem.get('Name', '')
        func_arg = func_elem.get('Arg', '')
        func_label = func_elem.get('Label', '')
        
        func_info = {
            'type': func_type,
            'name': func_name,
            'arguments': func_arg,
            'label': func_label,
            'returns': returns,
            'description': description,
            'section': section_name,
            'chapter': chapter_name,
            'full_description': f"Description: {description}. Requires loading \"{package_name}\"."
        }
        
        if not sanity_check_tool(func_name, tools, exclude_subwords):
            continue
        
        functions.append(func_info)
    
    return functions


def parse_gap_xml(xml_file: str, package_name: str, tools: List[str], exclude_subwords: List[str]) -> Dict[str, Any]:
    """Parse a GAP documentation XML file and extract all functions/methods."""
    
    # Load and preprocess XML
    # print(f"  * Parsing XML file: {xml_file}")
    
    # Preprocess XML to handle entities
    xml_content = preprocess_xml(xml_file)
    
    # Parse the preprocessed content
    root = ET.fromstring(xml_content)
    
    # Get chapter name
    chapter_heading = root.find('.//Heading')
    chapter_name = extract_text(chapter_heading) if chapter_heading is not None else "Unknown Chapter"
    
    all_functions = []
    
    # Find all sections
    sections = root.findall('.//Section')
    
    for section in sections:
        # Get section name
        section_heading = section.find('.//Heading')
        section_name = extract_text(section_heading) if section_heading is not None else "Unknown Section"
        
        # Find all ManSection elements in this section
        mansections = section.findall('.//ManSection')
        
        for mansection in mansections:
            functions = parse_mansection(mansection, chapter_name, section_name, package_name, tools, exclude_subwords)
            all_functions.extend(functions)
    
    return {
        'chapter': chapter_name,
        'functions': all_functions,
        'total_count': len(all_functions)
    }


def parse_multiple_xml_files(xml_files: List[str], package_name: str, tools: List[str], exclude_subwords: List[str]) -> Dict[str, Any]:
    """Parse multiple GAP documentation XML files."""
    all_data = {
        'chapters': [],
        'functions': [],
        'total_count': 0
    }
    
    for xml_file in xml_files:
        result = parse_gap_xml(xml_file, package_name, tools, exclude_subwords)
        all_data['chapters'].append(result['chapter'])
        all_data['functions'].extend(result['functions'])
        all_data['total_count'] += result['total_count']
    
    return all_data


def save_to_json(data: Dict[str, Any], output_file: str):
    """Save the extracted data to a JSON file."""
    total_tools = len(data.get('tools', []))
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {total_tools} tool(s) to {output_file}")


def generate_mcp_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an MCP-compatible schema from the extracted data."""
    tools = []
    
    for func in data['functions']:
        tool = {
            'name': func['name'],
            'description': func['full_description'],
            'inputSchema': {
                'type': 'object',
                'properties': {},
                'required': []
            }
        }
        
        # Parse arguments (simplified - you may need more sophisticated parsing)
        if func['arguments']:
            args = [arg.strip() for arg in func['arguments'].split(',')]
            if func['label']:
                label = func['label'][4:]
                args_types = [ "The type of this argument in the GAP-System is `" + arg_type.strip() + "`" for arg_type in label.split(',')]
            if len(args) == len(args_types):
                for arg, arg_type in zip(args, args_types):
                    tool['inputSchema']['properties'][arg] = {
                        'type': 'string',
                        'description': arg_type
                    }
                    tool['inputSchema']['required'].append(arg)
            else:
                for arg in args:
                    tool['inputSchema']['properties'][arg] = {
                        'type': 'string',
                        'description': 'Argument (in the GAP System)'
                    }
                    tool['inputSchema']['required'].append(arg)
        
        tools.append(tool)
    
    return {
        'tools': tools
    }

def extract_tools_from_gap_package(gap_package_path: str, package_name: str, gap_config: Dict[str, Any]):
    """Process GAP documentation XML files in the given path."""
    
    # Make sure the path is valid
    p = Path(gap_package_path).expanduser()
    if not p.exists() or not p.is_dir():
        print(f"Warning: The provided GAP package path '{gap_package_path}' is invalid.")
        return
    
    # Get package-specific tools list
    tools = tools_to_extract_list(gap_config, package_name)
    
    # Get package-specific exclude subwords
    exclude_subwords = exclude_subwords_list(gap_config, package_name)
    
    xml_files = list(p.joinpath("doc").rglob('*_Chapter_*.xml'))
    all_data = parse_multiple_xml_files([str(f) for f in xml_files], package_name, tools, exclude_subwords)
    mcp_tools = generate_mcp_schema(all_data)
    tools_dir = Path(__file__).parent.resolve() / "files" / "packages"
    destination_path = Path(tools_dir) / f"{package_name}.json"
    save_to_json(mcp_tools, str(destination_path))
    return

def gap_packages_paths(packages) -> List[tuple]:
    """Generate GAP package paths based on PACKAGES list. Returns list of (name, path) tuples."""
    paths = []
    for package_name in packages:
      code = f'exists := "{package_name.lower()}" in RecNames(GAPInfo.PackagesInfo);;'
      code += 'if exists = false then path := ""; else '
      code += f'package_info := GAPInfo.PackagesInfo.{package_name.lower()};;'
      code += 'p := PositionProperty( package_info, info -> PositionSublist( info.InstallationPath, ".gap" ) <> fail );;'
      code += 'if p <> fail then path := package_info[p].InstallationPath; else path := package_info[1].InstallationPath; fi;'
      code += 'fi;'
      code += 'path;'
      path = gap(code).strip().strip('"')
      
      if path == "":
        print(f"\033[38;5;208mWarning: Could not find installation path for GAP package '{package_name}'. Skipping.\033[0m")
      else:
        paths.append((package_name, path))
    
    return paths
  
def extract_gap_tools(gap_config):
    """Process GAP packages requested in config.yml and extract tools."""
    
    packages = get_packages_list(gap_config)
    
    for package_name, gap_package_path in gap_packages_paths(packages):
        print("--------------------------------")
        print(f"Processing GAP package: {gap_package_path}")  
        extract_tools_from_gap_package(gap_package_path, package_name, gap_config)
    return

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

    config_path = args.config_path
    print(f"Using configuration file: {config_path}")
    gap_config = load_gap_config(config_path)
    extract_gap_tools(gap_config)
