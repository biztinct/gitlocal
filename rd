  #!/bin/bash

  # Function to copy all health modules
  copy_all_health() {
      echo "Copying all pb_* modules..."
      scp -r /Users/adity/Documents/GitHub/gitlocal/pb_* Payobook19:/odoo/odoo-server/addons/
  }

  # Function to copy specific modules
  copy_specific() {
      echo "Copying specified modules: $@"
      scp -r "/Users/adity/Documents/GitHub/gitlocal/$@" Payobook19:/odoo/odoo-server/addons/
  }

  # Function to list available health modules
  list_health_modules() {
      echo "Available health modules:"
      ls -d /Users/adity/Documents/GitHub/gitlocal/pb_*/ 2>/dev/null | sed 's|/||g' | nl
  }

  # Main logic
  case "$1" in
      "all")
          copy_all_health
          ;;
      "list")
          list_health_modules
          ;;
      "")
          echo "Usage: $0 [all|list|module1 module2 ...]"
          echo "Examples:"
          echo "  $0 all                              # Copy all health_* modules"
          echo "  $0 list                             # List available modules"
          echo "  $0 health_base health_invoicing     # Copy specific modules"
          list_health_modules
          ;;
      *)
          copy_specific "$@"
          ;;
  esac
