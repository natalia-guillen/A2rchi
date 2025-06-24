from jinja2 import Environment, FileSystemLoader

template_dir = r"C:\Users\UAH\Desktop\A2rchi\a2rchi\templates"
template_file = "base-config.yaml"

context = {
    "name": "a2rchi",
    "collection_name": "a2rchi_collection",
    "postgres_hostname": "postgres-prueba",
    "global": {
        "TRAINED_ON": "",
        "DATA_PATH": "/root/data/",
        "ACCOUNTS_PATH": "/root/.accounts/",
        "LOCAL_VSTORE_PATH": "/root/data/vstore/",
        "ACCEPTED_FILES": [".txt", ".html", ".pdf"],
    },
    "interfaces": {
        "chat_app": {
            "PORT": 7861,
            "EXTERNAL_PORT": 7861,
            "HOST": "0.0.0.0",
            "HOSTNAME": "localhost",
            "template_folder": "/root/A2rchi/a2rchi/interfaces/chat_app/templates",
            "static_folder": "/root/A2rchi/a2rchi/interfaces/chat_app/static",
            "num_responses_until_feedback": 3,
            "include_copy_button": False,
        },
        "uploader_app": {
            "PORT": 5001,
            "EXTERNAL_PORT": 5003,
            "HOST": "0.0.0.0",
            "template_folder": "/root/A2rchi/a2rchi/interfaces/uploader_app/templates",
        },
        "grafana": {
            "EXTERNAL_PORT": 3000,
        }
    },
    "chains": {
        "input_lists": [],
        "base": {
            "ROLES": ["User", "A2rchi", "Expert"],
            "logging": {
                "input_output_filename": "chain_input_output.log"
            }
        },
        "prompts": {},
        "chain": {
            "MODEL_NAME": "OpenAIGPT4",
            "CONDENSE_MODEL_NAME": "OpenAIGPT4",
            "SUMMARY_MODEL_NAME": "OpenAIGPT4",
            "MODEL_CLASS_MAP": {
                "AnthropicLLM": {
                    "class": "AnthropicLLM",
                    "kwargs": {
                        "model_name": "claude-3-opus-20240229",
                        "temperature": 1
                    }
                },
                "OpenAIGPT4": {
                    "class": "OpenAILLM",
                    "kwargs": {
                        "model_name": "gpt-4",
                        "temperature": 1
                    }
                },
                "OpenAIGPT35": {
                    "class": "OpenAILLM",
                    "kwargs": {
                        "model_name": "gpt-3.5-turbo",
                        "temperature": 1
                    }
                },
                "DumbLLM": {
                    "class": "DumbLLM",
                    "kwargs": {
                        "sleep_time_mean": 3,
                        "filler": "null"
                    }
                },
                "LlamaLLM": {
                    "class": "LlamaLLM",
                    "kwargs": {
                        "base_model": "meta-llama/Llama-2-7b-chat-hf",
                        "peft_model": "null",
                        "enable_salesforce_content_safety": True,
                        "quantization": True,
                        "max_new_tokens": 4096,
                        "seed": "null",
                        "do_sample": True,
                        "min_length": "null",
                        "use_cache": True,
                        "top_p": 0.9,
                        "temperature": 0.6,
                        "top_k": 50,
                        "repetition_penalty": 1.0,
                        "length_penalty": 1,
                        "max_padding_length": "null"
                    }
                },
                "HuggingFaceOpenLLM": {
                    "class": "HuggingFaceOpenLLM",
                    "kwargs": {
                        "base_model": "Qwen/Qwen2.5-14B-Instruct-1M",
                        "peft_model": "null",
                        "enable_salesforce_content_safety": True,
                        "quantization": True,
                        "max_new_tokens": 4096,
                        "seed": "null",
                        "do_sample": True,
                        "min_length": "null",
                        "use_cache": True,
                        "top_p": 0.9,
                        "temperature": 0.6,
                        "top_k": 50,
                        "repetition_penalty": 1.0,
                        "length_penalty": 1,
                        "max_padding_length": "null"
                    }
                }
            },
            "chain_update_time": 10
        }
    },
    "utils": {
        "postgres": {
            "port": 5432,
            "user": "a2rchi",
            "database": "a2rchi-db"
        },
        "data_manager": {
            "CHUNK_SIZE": 1000,
            "CHUNK_OVERLAP": 0,
            "use_HTTP_chromadb_client": True,
            "chromadb_host": "chromadb",
            "chromadb_port": 8000,
            "chromadb_external_port": 8000,
            "reset_collection": True
        },
        "embeddings": {
            "EMBEDDING_NAME": "OpenAIEmbeddings",
            "EMBEDDING_CLASS_MAP": {
                "OpenAIEmbeddings": {
                    "class": "OpenAIEmbeddings",
                    "kwargs": {
                        "model": "text-embedding-3-small"
                    },
                    "similarity_score_reference": 0.4
                },
                "HuggingFaceEmbeddings": {
                    "class": "HuggingFaceEmbeddings",
                    "kwargs": {
                        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
                        "model_kwargs": {
                            "device": "cpu"
                        },
                        "encode_kwargs": {
                            "normalize_embeddings": True
                        }
                    },
                    "similarity_score_reference": 0.9
                }
            }
        },
        "scraper": {
            "reset_data": True,
            "verify_urls": False,
            "enable_warnings": False
        },
        "piazza": {
            "network_id": "m0g3v0ahsqm2lg"
        },
        "cleo": {
            "cleo_update_time": 10
        },
        "mailbox": {
            "IMAP4_PORT": 143,
            "mailbox_update_time": 10
        }
    }
}

env = Environment(loader=FileSystemLoader(template_dir))
template = env.get_template(template_file)
output = template.render(**context)

output_file = r"C:\Users\UAH\Desktop\A2rchi\config.yaml"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(output)

print(f"Archivo renderizado guardado en: {output_file}")


