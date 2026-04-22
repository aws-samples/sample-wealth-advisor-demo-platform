# Infrastructure as Code (IaC) - Roots Directory

---
## Table of Contents
- [IaaC Development Practices](#development-practices)
  - [Overview](#overview)
  - [Directory Structure](#directory-structure)
  - [Key Principles](#key-principles)
  - [Getting Started](#getting-started)
  - [How to Add New Components](#how-to-add-new-components)
  - [Best Practices](#best-practices)
---

## IaaC Development Practices 
### Overview
The `roots` directory contains all top-level Terraform projects. A top-level project is defined as a directory containing a `main.tf` file that requires direct `terraform apply` execution. Each top-level project maintains its own separate Terraform state file.

### Directory Structure
```
roots/
├── component-a/
│ ├── main.tf
│ ├── variables.tf
│ └── outputs.tf
├── component-b/
│ ├── main.tf
│ ├── variables.tf
│ └── outputs.tf
└── ...
```

### Key Principles

1. **Modular Design**
    - Top-level components should primarily compose reusable components and modules
    - All reusable components are located in the `templates` directory
    - Components should not define direct resource configurations; instead, use modules

2. **Component Structure**
   Each component directory should contain:
    - `main.tf` - Primary configuration file calling modules
    - `variables.tf` - Input variable declarations
    - `outputs.tf` - Output value declarations
    - `terraform.tfvars` (optional) - Variable assignments

3. **State Management**
    - Each component maintains its own state file
    - State files should be stored remotely (e.g., S3 bucket)
    - State locking should be enabled (e.g., using DynamoDB)

### Adding New Components

When adding a new component:

1. Create a new directory with a descriptive name
2. Include the standard files (main.tf, variables.tf, outputs.tf)
3. Reference existing modules from the templates directory
4. Document component-specific requirements in a component-level README.md [Optional]
5. Follow existing naming conventions and code style

### Best Practices

1. **Code Organization**
    - Keep configurations simple and focused
    - Use consistent formatting 
    - Follow established naming conventions

2. **Documentation**
    - Include clear descriptions for variables and outputs
    - Document any component-specific requirements
    - Maintain up-to-date README files

3. **Version Control**
    - Commit changes with clear, descriptive messages
    - Review changes before applying
    - Tag significant versions

4. **Testing**
    - Test configurations regularly by deploying and checking on the console

## Notes
- Do not modify shared modules directly; propose changes through proper channels
- Ensure all sensitive values are handled via variables
- Follow the principle of least privilege when defining IAM roles
