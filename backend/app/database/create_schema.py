import sys
import os
import logging
from dotenv import load_dotenv

# Weaviate v4 specific imports for schema creation
from weaviate.collections.classes.config import (
    Property,
    DataType,
    ReferenceProperty,
    Configure, # Use Configure for cleaner config
    Tokenization
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("create_schema")

current_dir = os.path.dirname(os.path.abspath(__file__))
# Load .env - similar logic as reset_db.py
env_path = os.path.join(current_dir, "..", "..", ".env") # Project root .env
if os.path.exists(env_path):
    logger.info(f"Loading .env from {env_path}")
    load_dotenv(env_path)
else:
    logger.warning("No .env file found. Relying on environment variables.")

# Add backend to sys.path
grand_parent_dir = os.path.dirname(os.path.dirname(current_dir))
if grand_parent_dir not in sys.path:
    sys.path.append(grand_parent_dir)

try:
    from app.database.weaviate_client import WeaviateClient
    from app.database.schema import WeaviateSchema
except ImportError as e:
    logger.error(f"Failed to import app modules: {e}")
    sys.exit(1)

def create_weaviate_schema():
    client_wrapper = None
    try:
        logger.info("Connecting to Weaviate...")
        client_wrapper = WeaviateClient()
        client = client_wrapper.client
        
        defined_schema = WeaviateSchema.get_schema()
        
        # Sort schema to create independent classes first
        # TCM_Standard_Ontology must be created before TCM_Reference_Case and TCM_Diagnostic_Rules
        ordered_schema = sorted(defined_schema, key=lambda x: 0 if x["class"] == "TCM_Standard_Ontology" else 1)
        
        logger.info("Applying schema to Weaviate...")
        
        for class_definition in ordered_schema:
            class_name = class_definition["class"]
            try:
                # Check if collection already exists
                if client.collections.exists(class_name):
                    logger.info(f"Collection '{class_name}' already exists. Skipping creation.")
                    continue
                else:
                    logger.info(f"Creating collection: {class_name}")
                    
                    config_properties = []
                    config_references = [] # Separate list for references
                    
                    for prop_def in class_definition.get("properties", []):
                        prop_name = prop_def["name"]
                        prop_data_types = prop_def["dataType"] 
                        
                        if prop_data_types[0] in ["text", "text[]", "number", "int", "date", "boolean"]:
                            # Regular property
                            weaviate_data_type = None
                            if prop_data_types[0] == "text":
                                weaviate_data_type = DataType.TEXT
                            elif prop_data_types[0] == "text[]":
                                weaviate_data_type = DataType.TEXT_ARRAY # Correct mapping for arrays
                            elif prop_data_types[0] == "int":
                                weaviate_data_type = DataType.INT
                            elif prop_data_types[0] == "number":
                                weaviate_data_type = DataType.NUMBER
                            elif prop_data_types[0] == "date":
                                weaviate_data_type = DataType.DATE
                            elif prop_data_types[0] == "boolean":
                                weaviate_data_type = DataType.BOOL
                            
                            # Handle Tokenization Enum
                            tokenization_val = None
                            if prop_def.get("tokenization") == "field":
                                tokenization_val = Tokenization.FIELD
                            
                            config_properties.append(Property(
                                name=prop_name,
                                data_type=weaviate_data_type,
                                tokenization=tokenization_val,
                                description=prop_def.get("description")
                            ))
                        else: # Reference property
                            config_references.append(ReferenceProperty(
                                name=prop_name,
                                target_collection=prop_data_types[0],
                                description=prop_def.get("description")
                            ))

                    # Direct creation using client.collections.create
                    client.collections.create(
                        name=class_name,
                        description=class_definition.get("description"),
                        properties=config_properties,
                        references=config_references, # Pass references separately
                        vectorizer_config=Configure.Vectorizer.none(), # Correct v4 way for BYOV
                    )
                    logger.info(f"Created collection: {class_name}")
            except Exception as e:
                logger.error(f"Error creating collection {class_name}: {e}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        logger.error(f"Failed to apply Weaviate schema: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client_wrapper:
            client_wrapper.close()

if __name__ == "__main__":
    create_weaviate_schema()