# tools.py

def plugin_image_guideline(stage: str, message: str = "") -> str:
    """
    Returns a human-friendly explanation of Pre-Image/Post-Image availability in D365 plugins.
    Example usage: plugin_image_guideline("PreOperation", "update")
    """
    guidelines = {
        "PreValidation": (
            "Pre-Validation Stage:\n"
            "- No Pre-Image (operation hasn't occurred yet; rarely used)\n"
            "- No Post-Image\n"
            "Best practice: Images rarely useful here—this is for initial validation only."
        ),
        "PreOperation": (
            "Pre-Operation Stage:\n"
            "- ✅ Pre-Image (data before operation)\n"
            "- ❌ Post-Image (not available yet)\n"
            "Use Pre-Image if you need to compare prior values or perform validation before commit."
        ),
        "PostOperation": (
            "Post-Operation Stage:\n"
            "- ✅ Pre-Image (data before operation)\n"
            "- ✅ Post-Image (data after operation)\n"
            "Use both Pre-Image and Post-Image for audit, integration, or checking actual committed changes."
        ),
    }
    return guidelines.get(stage, "Unknown plugin stage. Please specify PreValidation, PreOperation, or PostOperation.")

def plugin_image_suggestion(message: str, stage: str) -> dict:
    """
    Suggests which images are available/needed based on plugin message and stage.
    """
    # Typical message-to-image mapping for main CRUD/plugin events
    lookup = {
        "create": {
            "PreValidation":  {"pre": False, "post": False},
            "PreOperation":   {"pre": False, "post": False},
            "PostOperation":  {"pre": False, "post": True},   # Post-Image available after create
        },
        "update": {
            "PreValidation":  {"pre": False, "post": False},
            "PreOperation":   {"pre": True,  "post": False},
            "PostOperation":  {"pre": True,  "post": True},
        },
        "delete": {
            "PreValidation":  {"pre": False, "post": False},
            "PreOperation":   {"pre": True,  "post": False},
            "PostOperation":  {"pre": True,  "post": False},
        },
        "assign": {
            "PreValidation":  {"pre": False, "post": False},
            "PreOperation":   {"pre": True,  "post": False},
            "PostOperation":  {"pre": True,  "post": True},
        },
        # Add more messages as needed
    }

    msg = message.lower()
    stage = stage  # should be PreValidation, PreOperation, PostOperation

    if msg in lookup and stage in lookup[msg]:
        avail = lookup[msg][stage]
        return {
            "PreImageAvailable": avail["pre"],
            "PostImageAvailable": avail["post"],
            "Recommended": (
                "Use Pre-Image if you need previous values."
                if avail["pre"] else ""
            ) + (
                " Use Post-Image for values after operation."
                if avail["post"] else ""
            )
        }
    else:
        return {
            "PreImageAvailable": False,
            "PostImageAvailable": False,
            "Recommended": "Not a standard combination. Check plugin docs."
        }
