from __future__ import annotations

import hashlib
import json

from types import MappingProxyType
from typing import Any, Mapping

from modules.developer.developer_task_execution_dependency_profile_policy import (
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY as _CURRENT_DEPENDENCY_PROFILE_POLICY,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT as _CURRENT_DEPENDENCY_PROFILE_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID as _CURRENT_DEPENDENCY_PROFILE_POLICY_ID,
    developer_task_execution_dependency_profile_policy_fingerprint as _current_dependency_profile_policy_fingerprint,
    validate_developer_task_execution_dependency_profile_policy as _validate_current_dependency_profile_policy,
)


DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_ID = (
    "skynetvs-v1c3a1a-non-network-dependency-acquisition-contract-v1"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_FINGERPRINT = (
    "5ed6c7bd3e1c3b180fc7344fb5078d3279ad9b597553fe25bf75cd5d45964dac"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_ID = (
    "skynetvs-v1c3a1-target-matched-resolver-mediated-acquisition-lock-v1"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT = (
    "65649ffa282db0b625c58f687adb16e1b41d5f5ada679985ee7dde4d77e61d73"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_ID = (
    "skynetvs-v1c0b2-external-source-authority-lock-v1"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT = (
    "80da155e8de0ce9f6d17565541173b701c2d5c9c8a8c13f1fcab9a57dbdb3d5e"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_ID = (
    "skynetvs-v1c3a0-dependency-profile-target-contract-v1"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT = (
    "370e5d2c246be240b9d1a47fdebcc1250302155ea0e6128b6580079d5691748a"
)

_RC043_POLICY_CANONICAL_JSON = '{"active_component_identity":{"before_first_use_each_component_must_bind":["committed Git mode, type, blob ID, path, byte count and SHA-256","complete project-owned import closure and file manifest SHA-256","interpreter/runtime executable and standard-library identity","ordered argv, working directory, stdin/stdout/stderr and environment contract","no dynamic plugin, user site, host site-packages or PATH import"],"component_runtime_not_selected_by_rc043":true,"components":["resolver launcher and argv builder","mediation broker and upstream HTTP/TLS client","Simple JSON parser and resolver-view generator","Core Metadata and requirement/marker parser","wheel archive metadata reader","egress/confinement launcher and verifier","resolver-tool wheel/RECORD/license verifier","resolver-tool deterministic extractor and capsule-tree verifier","SPDX License-Expression validator used for resolver-tool acceptance"],"identities_in_deterministic_closure":true,"source_review_and_host_only_active_proof_required":true},"active_worker_confinement":{"applies_to":["resolver worker","broker worker","archive-metadata worker"],"child_process_creation_denied":true,"credential_stores_and_user_profile_outside_attempt_root_access":false,"exact_mechanism_not_selected_by_rc043":true,"fresh_job_object_required":true,"host_only_confinement_proof_required_before_first_untrusted_byte_parse":true,"kill_on_job_close":true,"no_inherited_handles":true,"repository_and_stable_v1b4_write_access":false,"resolver_capsule_read_only_during_use":true,"restricted_non_administrative_token_required":true,"separate_processes":true,"writable_paths":["fresh external attempt root only"]},"bounds":{"connect_timeout_seconds":10,"integer_overflow_or_limit_exhaustion":"fail closed","max_candidate_metadata_compression_ratio":100,"max_candidate_metadata_members":1,"max_candidate_metadata_uncompressed_bytes":4194304,"max_compatible_wheel_records_per_project":256,"max_core_metadata_bytes":4194304,"max_core_metadata_header_fields":8192,"max_core_metadata_line_bytes":65536,"max_dependency_graph_edges":1024,"max_dependency_graph_nodes":128,"max_distinct_projects":128,"max_http_requests":2048,"max_json_array_items":16384,"max_json_object_members":16384,"max_json_string_utf8_bytes":4194304,"max_loopback_requests":8192,"max_marker_ast_nodes":1024,"max_marker_nesting_depth":64,"max_provenance_bytes":4194304,"max_requirement_utf8_bytes":8192,"max_requires_dist_fields":4096,"max_resolver_tool_archive_entries":4096,"max_resolver_tool_compression_ratio_each":100,"max_resolver_tool_extracted_file_bytes_each":67108864,"max_resolver_tool_extracted_total_bytes":268435456,"max_resolver_tool_license_file_bytes_each":4194304,"max_resolver_tool_license_files":512,"max_resolver_tool_metadata_bytes":4194304,"max_resolver_tool_record_bytes":16777216,"max_resolver_tool_record_path_utf8_bytes":4096,"max_resolver_tool_record_rows":4096,"max_resolver_tool_regular_files":4096,"max_resolver_tool_total_license_bytes":67108864,"max_resolver_tool_wheel_bytes":67108864,"max_resolver_tool_wheel_metadata_bytes":1048576,"max_response_headers_bytes":65536,"max_selected_wheels":256,"max_simple_file_records_per_project":8192,"max_simple_response_bytes":16777216,"max_total_metadata_bytes":268435456,"max_total_wheel_bytes":2147483648,"max_url_bytes":4096,"max_wheel_archive_entries":16384,"max_wheel_bytes_each":268435456,"max_wheel_central_directory_bytes":8388608,"max_wheel_member_extra_bytes":65536,"max_wheel_member_name_utf8_bytes":1024,"read_idle_timeout_seconds":60,"request_deadline_seconds":180,"resolver_deadline_seconds":1800,"resolver_report_bytes":33554432,"stderr_bytes":8388608,"stdout_bytes":8388608,"tls_timeout_seconds":15},"candidate_manifest":{"array_ordering":{"artifacts":"normalized name, canonical version, filename, SHA-256","attestations":"publisher kind, subject filename, statement SHA-256","dependency_edges":"parent, child, specifier, marker","licenses":"wheel path","projects":"normalized project name","requests":"monotonic request ordinal"},"canonical_encoding":"UTF-8 without BOM, LF, final LF","canonical_json":{"allow_nan":false,"ensure_ascii":false,"separators":[",",":"],"sort_object_keys":true},"canonical_material_includes":["policy ID and fingerprint","Git baseline and declaration object identities","profile and fixed-target contract fingerprints","resolver capsule Python, pip wheel, extracted-tree and entry-point identities","ordered argv and environment fingerprints","egress-guard evidence identity","exact Simple/Core Metadata/provenance response identities","package graph and marker decisions","wheel URLs, filenames, sizes and declared/actual SHA-256","request ledger and all enforced bounds","canonical logical resolver-view projection bytes and SHA-256","canonical stable route-map projection and resolver-to-authority reconciliation","canonical resolver-proposal projection bytes and SHA-256","exact active component code/runtime identities","V1C0B2 decision ID/fingerprint and current committed lock-block cross-check","V1C3A0 policy ID/fingerprint/source blob and dependency-profile report cross-check","resolver-tool create-once RECORD/license/source-security acceptance identity"],"eligible_for_v1c3b":false,"execution_authority":false,"role":"non-authoritative candidate only","run_envelope_binds_canonical_manifest_sha256":true,"volatile_fields_excluded_from_closure_fingerprint":["wall-clock timestamps","process IDs","absolute temporary paths","ephemeral ports","attempt route tokens","raw served resolver-view bytes","raw resolver-report bytes","actual loopback URLs","unpinned resolver-report environment fields"],"volatile_transport_evidence":{"bound_in_attempt_run_envelope":true,"excluded_from_deterministic_closure_fingerprint":["wall-clock request timing","DNS answer ordering","peer IP","TLS version","TLS cipher","leaf certificate SHA-256","transport-only response headers"],"selection_critical_http_facts_in_closure":["authoritative URL","HTTP status","media type","content encoding","raw body byte count","raw body SHA-256"]}},"decision_id":"skynetvs-v1c3a1-target-matched-resolver-mediated-acquisition-lock-v1","entering_baseline":{"branch":"main","head":"aa01155fb5b015faabc4aaf297c6cd7906334d9d","tree":"a2b8a22df5015976e269e006c9a33dfb5d60512d","v1c3a0":"IMPLEMENTED / VERIFIED / PUSHED / DOCS CLOSED / NON-AUTHORIZING","v1c3a1":"NOT OPEN"},"environment":{"allowed_names":["SYSTEMROOT","WINDIR","COMSPEC","TEMP","TMP","PATH","PATHEXT","USERPROFILE","HOME","APPDATA","LOCALAPPDATA","PYTHONUTF8","PYTHONDONTWRITEBYTECODE","PYTHONNOUSERSITE","PYTHONHASHSEED","PYTHONSAFEPATH"],"applies_to":["resolver worker","broker worker","Simple/Core Metadata parser worker","wheel archive metadata worker"],"config_absence_or_disablement_must_be_proven_from_exact_pip_source_before_first_use":true,"constructed_from_empty_template":true,"fresh_attempt_user_temp_cache_roots":true,"inherited_environment":false,"keyring":false,"netrc":false,"path_contains_capsule_and_system_minimum_only":true,"pinned_python_values":{"PYTHONDONTWRITEBYTECODE":"1","PYTHONHASHSEED":"0","PYTHONNOUSERSITE":"1","PYTHONSAFEPATH":"1","PYTHONUTF8":"1"},"pip_no_config_and_keyring_mode":"must be selected and proven from exact accepted pip source; --isolated alone is not accepted as proof of global-config absence","proxy_inheritance":false,"scrub_exact_names":["HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","NO_PROXY","http_proxy","https_proxy","all_proxy","no_proxy","REQUESTS_CA_BUNDLE","CURL_CA_BUNDLE","SSL_CERT_FILE","SSL_CERT_DIR","NETRC","VIRTUAL_ENV","PIP_CONFIG_FILE","PIP_INDEX_URL","PIP_EXTRA_INDEX_URL","PIP_TRUSTED_HOST","PIP_CERT","PIP_CLIENT_CERT","PIP_PROXY","PIP_NO_INDEX","PIP_FIND_LINKS","PIP_CACHE_DIR","PIP_REQUIRE_VIRTUALENV"],"scrub_prefixes":["PIP_","PYTHON","XDG_","UV_"],"shell":false,"stdin":"closed / null device","user_or_global_pip_config":false,"values_with_credentials_may_be_serialized":false,"working_directory":"fresh external attempt root"},"evidence_layers":{"attempt_run_envelope":{"binds":["raw upstream response bytes and SHA-256","raw served resolver-view bytes and SHA-256","actual numeric loopback host/port and attempt route token","raw resolver report bytes and SHA-256","raw stdout and stderr bytes and SHA-256","absolute attempt paths and process identities","DNS/TLS/peer/header/timing transport observations","canonical closure manifest SHA-256"],"eligible_for_deterministic_closure_fingerprint":false,"role":"create-once attempt-specific evidence"},"deterministic_closure_projection":{"binds":["canonical authority objects","stable logical object IDs and route-map projection","canonical resolver-view projection bytes and SHA-256","canonical resolver-proposal projection bytes and SHA-256","pinned target environment projection","normalized package graph and marker/extra decisions","selected artifact identities and request ordinal projection"],"must_not_contain":["actual loopback port","attempt route token","absolute temporary path","process ID","wall-clock timestamp","raw resolver report URL","unpinned resolver-report environment value","DNS answer ordering","peer IP","TLS version or cipher","leaf certificate SHA-256","transport-only response header"],"role":"canonical non-authoritative candidate closure material"}},"extras_contract":{"extra_marker_allowed_in_requires_dist":true,"extra_marker_evaluation_values":[""],"graph_wide_nonempty_requested_extras":"fail closed","independent_parser_and_resolver_extra_decisions_must_match":true,"initial_profile_requested_extras":[],"provides_extra":"evidence only; does not activate an extra","resolver_report_or_graph_with_nonempty_extras":"fail closed","root_requirement_extras":"must be empty","transitive_requirement_extras":"must be empty"},"failure_and_storage":{"cleanup_may_not_delete_committed_evidence":true,"content_addressed_objects":true,"create_once_evidence":true,"failed_attempt_preserved":true,"fallback_to_host_cache_index_proxy_direct_url_sdist_or_build":false,"fresh_external_attempt_root":true,"overwrite_replace_or_rename_finalize_existing_evidence":false,"partial_candidate_promotable":false,"same_attempt_rerun":false,"terminal_result_create_once":true},"fixed_target":{"implementation_name":"cpython","implementation_version":"3.13.15","os_name":"nt","platform_machine":"AMD64","platform_python_implementation":"CPython","platform_system":"Windows","python_full_version":"3.13.15","python_version":"3.13","requested_extras":[],"sys_platform":"win32"},"gates":{"active_component_code_and_runtime_identity_must_be_bound_before_first_use":true,"active_dependency_acquisition_requires_separate_host_only_preflight_and_final_launcher":true,"archive_and_metadata_exact_bounds_must_be_enforced":true,"attempt_vs_closure_projection_contract_must_be_implemented_and_tested":true,"broker_os_egress_guard_must_be_proven_before_first_external_request":true,"candidate_dependency_import_or_execution":false,"copied_scope_and_target_must_equal_current_v1c3a0_policy":true,"docs_lock_authorizes_network":false,"execution_authorized":false,"graph_wide_no_extras_contract_must_be_enforced":true,"resolver_egress_guard_must_be_proven_before_first_use":true,"resolver_tool_bootstrap_requires_separate_host_only_preflight_and_final_launcher":true,"resolver_tool_exact_version_selected_by_rc043":false,"resolver_tool_import_or_version_smoke_before_acceptance":false,"resolver_tool_manual_create_once_acceptance_required":true,"resolver_tool_record_license_and_security_acceptance_required_before_first_execution":true,"reusable_lease":false,"sandbox_launch":false,"v1c0b2_external_source_authority_lineage_cross_check_required":true,"v1c3a0_dependency_profile_target_lineage_cross_check_required":true,"v1c3a1a_authorizes_network":false,"v1c3a2_offline_verification_required":true,"v1c3a3_manual_immutable_acceptance_required":true,"worker_process_filesystem_confinement_must_be_proven_before_first_use":true},"initial_scope":{"blocked_profiles":["skynetvs-nlu-training-minimal-v1","skynetvs-python-base-whisper-v1"],"declaration_paths":["requirements.txt"],"profile_id":"skynetvs-python-base-v1","requested_extras":[],"scope_expansion_requires_separate_roadmap_decision":true},"internal_sequence":[{"artifact_bytes":false,"authority":false,"id":"V1C3A1A","name":"non-network acquisition contract","network":false,"resolver_execution":false},{"artifact_role":"resolver-tool candidate only","authority":false,"id":"V1C3A1B","name":"target-matched resolver capsule bootstrap and offline tool verification","network":"separate broker-only resolver-tool acquisition gate","resolver_execution":false},{"artifact_role":"non-authoritative dependency candidate","authority":false,"id":"V1C3A1C","name":"bounded mediated candidate acquisition","network":"project-owned broker only","resolver_execution":"target-matched capsule under egress guard"}],"marker_contract":{"bound_environment_values":{"implementation_name":"cpython","implementation_version":"3.13.15","os_name":"nt","platform_machine":"AMD64","platform_python_implementation":"CPython","platform_system":"Windows","python_full_version":"3.13.15","python_version":"3.13","requested_extras":[],"sys_platform":"win32"},"evaluation_engine":"accepted target-capsule pip marker evaluator, independently rechecked by a project-owned strict parser","explicitly_unpinned_forbidden_variables":["platform_release","platform_version"],"marker_parse_required_before_name_authorization":true,"nonempty_requested_extra_anywhere":"fail closed","other_forbidden_variables":["dependency_groups"],"requested_extra_values":[""],"requirement_name_extras_anywhere":"fail closed","requires_dist_marker_allowed_variables":["implementation_name","implementation_version","os_name","platform_machine","platform_python_implementation","platform_system","python_full_version","python_version","sys_platform","extra"],"resolver_and_independent_parser_decisions_must_match":true,"root_and_transitive_marker_decisions_recorded":true,"root_marker_allowed_variables":["implementation_name","implementation_version","os_name","platform_machine","platform_python_implementation","platform_system","python_full_version","python_version","sys_platform"],"unknown_marker_variable":"fail closed","unsupported_marker_operator_or_syntax":"fail closed"},"network_model":{"active_use_requires_host_only_egress_proof":true,"broker":{"accept_encoding":"identity","authorized_project_name_sources":["exact committed root declaration","strictly parsed Requires-Dist from previously captured authoritative Core Metadata"],"automatic_retries":0,"bind_host":"127.0.0.1","derived_loopback_responses_are_authority":false,"ephemeral_port":true,"external_response_bytes_preserved_exactly":true,"max_in_flight_upstream_requests":1,"only_external_network_actor":true,"project_owned":true,"resolver_requested_names_are_authority":false,"resolver_view":{"allowed_method_status_range_surface_requires_exact_pip_source_audit_before_first_use":true,"canonical_logical_view":{"actual_port_and_attempt_token_absent":true,"bytes_and_sha256_in_closure":true,"deterministic_ordering":true,"stable_logical_object_ids":true},"exact_route_to_authoritative_url_filename_size_sha256_mapping_required":true,"external_urls_never_exposed_to_resolver":true,"file_and_metadata_urls_rewritten_to_attempt_local_loopback_object_routes":true,"raw_upstream_simple_bytes_are_authority":true,"resolver_report_names_urls_and_artifacts_must_map_exactly_to_view_and_authority_ledger":true,"resolver_view_bytes_and_sha256_captured":true,"resolver_view_is_authority":false,"route_map_projection":{"actual_route_path_and_token_in_attempt_envelope_only":true,"canonical_entries_bind":["stable logical route ID","authority class","canonical authoritative URL","normalized project name","filename when applicable","declared byte size when applicable","declared SHA-256 when applicable"]},"served_attempt_view":{"actual_numeric_loopback_base_substituted":true,"derived_from_canonical_logical_view":true,"eligible_for_closure_fingerprint":false,"exact_bytes_and_sha256_in_attempt_envelope_only":true},"strict_parse_before_view_generation":true,"unknown_method_route_range_or_object":"fail closed"},"serial_upstream_requests":true,"single_attempt_route":true},"broker_egress_guard":{"allow_dns_only_to_exact_configured_resolver_set":true,"allow_tcp_only_to_port_443_public_peer_set_for_allowlisted_hosts":true,"application_hostname_sni_and_certificate_checks_still_required":true,"default_deny":true,"host_only_proof_required_before_first_external_request":true,"mechanism_not_selected_by_rc043":true},"broker_os_egress_guard_required":true,"canonical_url_rules":{"fragment":false,"implicit_port":443,"query":false,"redirects_allowed":0,"relative_or_scheme_relative_urls":false,"scheme":"https","simple_project_path":"/simple/<normalized-project>/","trailing_slash_required":true,"unicode_host":false,"userinfo":false},"dns_and_tls":{"client_certificate":false,"custom_ca":false,"default_system_trust_only":true,"dns_only_for_exact_upstream_hosts":true,"hostname_verification":true,"minimum_tls":"1.2","reject_loopback_private_link_local_multicast_reserved_peer_addresses":true,"sni_and_host_must_match_allowlist":true,"tls_version_cipher_leaf_certificate_sha256_and_peer_ip_captured":true},"egress_guard_mechanism_not_selected_by_rc043":true,"http":{"allowed_status":[200],"authorization_headers":false,"content_encoding":"identity only","cookies":false,"credential_prompting":false,"redirect_statuses":"fail closed"},"resolver_external_network":false,"resolver_local_broker_namespace":{"attempt_route_token_entropy_bits_minimum":256,"attempt_route_token_source":"operating-system CSPRNG","bind_address":"127.0.0.1 only","exact Host header and attempt route required":true,"listener_ready_before_resolver_launch":true,"repeat resolver reads served from immutable captured object":true,"token_is_namespace_and_collision_defense_not_source_authority":true,"unsolicited_or_duplicate_requests_cannot_authorize_new_upstream_names":true,"upstream_authority_object_fetched_at_most_once":true},"resolver_loopback_only":true,"resolver_os_egress_guard_required":true,"upstream_origins":{"provenance_initial":["https://pypi.org:443"],"provenance_outside_initial_allowlist":"fail closed and require roadmap review","simple_json":["https://pypi.org:443"],"wheel_and_core_metadata":["https://files.pythonhosted.org:443"]}},"observed_host_resolver":{"blocking_issue_codes":["resolver_marker_environment_not_target_bound","resolver_host_python_full_version_mismatch"],"distribution_manifest_sha256":"a41debbc8862b902055f1b5b913cdf1a60d2323b814f91ff05091b9cdc51b81d","eligible":false,"host_python_full_version":"3.12.10","measured":true,"name":"pip","no_fallback":true,"selected":false,"version":"25.3","version_is_future_tool_pin":false},"resolver_capsule":{"host_python_3_12_fallback":false,"marker_environment_bound_keys_must_equal_fixed_target":true,"materialization":{"ensurepip":false,"exact_pth_bytes_required":true,"exact_tree_manifest_required":true,"fresh_external_root":true,"import_site":false,"no_inherited_site_packages":true,"no_user_site":true,"pip_install_for_bootstrap":false,"pip_wheel_deterministic_extraction":true,"source_copy_only":true},"python_source":{"bytes":11009825,"kind":"CPython Windows embeddable AMD64 ZIP","sha256":"d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf","version":"3.13.15"},"separate_from_project_venv":true,"separate_from_repository":true,"separate_from_stable_v1b4":true,"trusted_runtime_status":false,"unbound_marker_keys_must_not_be_referenced":true},"resolver_invocation":{"before_first_use_source_proof_must_lock":["retry count and resume-retry behavior","loopback connect/read timeout options","keyring fully disabled","global/user/site configuration fully disabled","allowed GET/HEAD/Range request surface","report schema and raw environment fields"],"build_backend_execution_forbidden":true,"entry_point_semantics":"target capsule python -m pip","exact_ordered_argv_and_sha256_required_before_first_use":true,"forbidden_options_or_inputs":["--extra-index-url","--find-links","--trusted-host","--proxy","--cert","--client-cert","--pre","--no-deps","--ignore-requires-python","editable requirements","direct URL requirements","VCS requirements","local project requirements","sdist candidates","local build candidates"],"install_phase_forbidden":true,"nonempty_extras_forbidden_graph_wide":true,"package_import_or_execution_forbidden":true,"required_options":["--isolated","--dry-run","--report=<fresh-external-path>","--ignore-installed","--only-binary=:all:","--no-cache-dir","--disable-pip-version-check","--no-input","--progress-bar=off","--platform=win_amd64","--python-version=3.13.15","--implementation=cp","--abi=cp313","--index-url=http://127.0.0.1:<ephemeral-port>/<attempt-route>/simple/","--requirement=<exact-canonical-requirements-copy>"],"role":"proposal only","shell_false":true,"stdin_closed":true,"stdout_stderr_and_report_bounds_required":true,"working_directory_is_fresh_attempt_root":true},"resolver_output":{"authority":false,"canonical_proposal_projection":{"absolute_paths_ports_tokens_timestamps_and_pids_excluded":true,"bytes_and_sha256_in_closure":true,"every_loopback_url_must_reconcile_through_route_map":true,"external_authority_identity_replaces_loopback_url":true,"only_pinned_target_environment_keys_retained":true,"resolver_and_independent_graph_must_match":true,"stable_array_ordering_required":true,"strict_parse_required":true,"unpinned_environment_keys_excluded":["platform_release","platform_version"]},"raw_report":{"attempt_run_envelope_only":true,"eligible_for_closure_fingerprint":false,"exact_bytes_and_sha256_required":true,"reason":"contains attempt-local loopback URLs and running-environment fields that are not all part of the fixed target"}},"resolver_tool_acceptance":{"acceptance_evidence":{"accepted_status_required_before_first_execution":true,"binds":["exact selected version and authoritative Simple response","wheel URL, filename, size and declared/actual SHA-256","provenance absence or verified presence","raw METADATA, WHEEL and RECORD identities","canonical RECORD projection","License-Expression and complete License-File manifest","deterministic extracted-tree manifest","exact source-semantics audit result","exact capsule Python/_pth/entry-point/import-closure identities","fresh security-advisory review identity"],"create_once_candidate_report":true,"create_once_manual_acceptance_result":true,"partial_or_failed_acceptance_promotable":false,"same_attempt_rerun":false},"archive_identity":{"allowed_compression_methods":["stored","deflate"],"allowed_top_level_prefixes":["pip/","<canonical-pip-name-version>.dist-info/"],"crc32_and_local_central_name_size_method_agreement_required":true,"duplicate_unicode_normalized_or_windows_casefolded_path":"reject","encrypted_symlink_hardlink_device_or_special_member":"reject","exactly_one_dist_info_directory_matching_name_version":true,"explicit_directory_entries":"canonical zero-length only; not RECORD files","forbidden_members_or_classes":["<dist-info>/RECORD.jws","<dist-info>/RECORD.p7s","<dist-info>/INSTALLER","<dist-info>/REQUESTED","<dist-info>/direct_url.json","*.pyc","__pycache__/","*.pyd","*.dll","*.exe","*.so","*.dylib","<name-version>.data/"],"overlapping_or_duplicate_local_ranges":"reject","prepended_trailing_or_concatenated_archive_payload":"reject","required_members":["<dist-info>/METADATA","<dist-info>/WHEEL","<dist-info>/RECORD","pip/__init__.py","pip/__main__.py"],"unique_zip_classification_required":true,"unsafe_absolute_drive_parent_backslash_nul_ads_or_reserved_windows_path":"reject"},"deterministic_extraction":{"capsule_tree_manifest_binds":["path","regular-file mode class","byte count","SHA-256"],"capsule_tree_manifest_sort":"Windows casefolded canonical relative path","directory_creation_derived_from_member_paths_only":true,"extract_only_record_bound_regular_members":true,"generated_installer_requested_direct_url_or_pyc_files":false,"manifest_bytes_and_sha256_required":true,"pip_install_or_wheel_installer_execution":false,"post_extract_every_file_must_equal_record_sha256_and_size":true,"project_owned_extractor_only":true,"resolver_capsule_read_only_before_and_during_first_use":true,"source_wheel_immutable_and_content_addressed":true,"unexpected_or_missing_extracted_file":"reject"},"exact_version_selected_by_rc043":false,"license_contract":{"acceptance_is_not_automatic_legal_inference":true,"automatic_inference_from_legacy_license_or_classifiers":false,"declared_license_file_set_must_equal_licenses_subtree_file_set":true,"declared_path_maps_to":"<dist-info>/licenses/<License-File value>","every_license_file_record_bound_with_exact_sha256_and_size":true,"exact_license_expression_and_sorted_license_manifest_in_acceptance":true,"legacy_license_and_license_expression_conflict":"reject","license_expression_must_be_valid_case_normalized_spdx":true,"license_expression_required_for_metadata_2_4":true,"license_file_content":"strict UTF-8 text","license_file_fields_required_minimum":1,"license_file_paths":"unique canonical forward-slash relative paths; no parent components","manual_explicit_license_evidence_acceptance_required":true},"record_contract":{"all_other_rows":{"accepted_hash_algorithm":"sha256 only","digest_encoding":"URL-safe base64 without padding; decodes to 32 bytes","digest_must_equal_uncompressed_member_sha256":true,"hash_field_required":true,"size_encoding":"canonical non-negative base-10 integer","size_field_required":true,"size_must_equal_uncompressed_member_bytes":true},"canonical_archive_relative_forward_slash_paths_only":true,"canonical_sorted_record_projection_and_sha256_required":true,"columns_per_row":3,"csv_dialect":"Python csv.reader default comma/double-quote dialect","duplicate_rows_or_case_collisions":"reject","encoding":"strict UTF-8 without BOM","raw_record_bytes_and_sha256_required":true,"record_self_row":{"exactly_one":true,"hash_field":"empty","size_field":"empty"},"record_signature_members":"forbidden","regular_file_member_set_equals_record_path_set":true,"unlisted_missing_or_nonexistent_file":"reject"},"required_before":["any import of pip from the resolver capsule","any target-capsule python -m pip invocation","any resolver process launch, including --version or offline smoke","any V1C3A1C dependency-resolution attempt"],"role":"pre-execution resolver-tool capability acceptance","selection_gate":{"authoritative_simple_and_wheel_evidence_required":true,"fresh_official_release_and_security_advisory_review_required":true,"fresh_security_advisory_review_required":true,"known_unresolved_issue_affecting_planned_use":"fail closed","manual_create_once_acceptance_required":true,"no_fallback_to_observed_project_venv_pip_25_3":true,"no_latest_range_or_automatic_upgrade_semantics":true,"source_semantics_must_be_reaudited_for_exact_acquired_wheel":true,"stage":"V1C3A1B"},"tool_family":"pip","wheel_metadata":{"build_field":"absent","console_script_generation_or_execution":false,"entry_point":"target capsule python -m pip via exact pip/__main__.py import closure","generator":"captured as evidence, not authority","metadata_version_for_selected_tool":"2.4 required; otherwise separate architecture review","name_must_equal_canonical_project":true,"requires_dist_count_must_equal_zero":true,"requires_python_must_admit_target":true,"root_is_purelib":true,"version_must_equal_selected_exact_version":true,"wheel_tags_exact":["py3-none-any"],"wheel_version":"1.0"},"wheel_selection":{"build_tag":"absent","canonical_project_name":"pip","compatibility_tags":["py3-none-any"],"data_directory":false,"exact_version":"selected only by create-once V1C3A1B acceptance","native_code_or_executable_payload":false,"pre_release":false,"requires_dist_fields":0,"requires_python_must_admit":"3.13.15","root_is_purelib":true,"sdist_or_local_build":false,"wheel_only":true,"yanked":false}},"resolver_tool_candidate":{"exact_version_selected":false,"executable_selected":false,"family":"pip","first_use_blocked":true,"observed_project_venv_version":"25.3","observed_version_is_candidate_authority":false,"selection_contract":{"RECORD_and_wheel_tree_verified_offline":true,"actual_acquired_wheel_source_semantics_must_be_reaudited":["marker environment behavior","loopback URL and response behavior","retry/resume/range behavior","configuration and keyring behavior","report schema and environment fields"],"canonical_name":"pip","declared_and_actual_sha256_equal":true,"exact_version_is_selected_by_rc043":false,"exact_version_requires_separate_v1c3a1b_acceptance":true,"fresh_security_advisory_review_required":true,"known_unresolved_issue_affecting_planned_use":"fail closed","license_declaration_and_License_File_evidence_required":true,"pre_release":false,"provenance_absence_or_verified_presence_required":true,"requires_python_must_admit_3_13_15":true,"version_range_or_latest_resolution":false,"version_substitution_or_fallback":false,"wheel_must_be_target_compatible":true,"wheel_only":true,"yanked":false},"selection_requirements":["authoritative exact pip project Simple API response","authoritative exact pip wheel bytes","index-declared and actual SHA-256 equality","offline wheel and RECORD verification","deterministic extraction-tree manifest","exact entry point and source-distribution manifest","exact resolver capsule Python identity","exact ordered argv bytes and SHA-256","exact environment manifest and SHA-256","exact resolver report bytes and SHA-256","marker-variable subset and target-bound environment proof","resolver loopback-view protocol and URL-reconciliation proof","restricted worker process/filesystem/child-process confinement proof","license declaration and declared License-File evidence","provenance absence or cryptographically verified presence","exact acquired wheel source-semantics audit before execution","exact retry, resume, timeout, keyring and configuration CLI/source contract","exact V1C0B2 decision ID/fingerprint lineage cross-check","exact V1C3A0 policy ID/fingerprint/source/report lineage cross-check","exact resolver-tool version selected only in V1C3A1B after fresh security review","strict wheel METADATA/WHEEL/RECORD member-set and SHA-256 verification","complete License-Expression and License-File manifest acceptance","create-once manual resolver-tool capability acceptance before any import or execution"],"version_selection_stage":"V1C3A1B only after authoritative acquisition and source/security review"},"roadmap_change":"RC043","schema_version":1,"source_authority":{"artifacts":{"direct_url":false,"extra_index":false,"filename_size_declared_sha256_actual_sha256_must_match":true,"host_cache":false,"local_build":false,"nonempty_dependency_extras":false,"origin":"https://files.pythonhosted.org","pre_release":false,"resolver_view_filters_out_ineligible_files_before_serving":true,"sdist":false,"url_must_come_from_verified_simple_response":true,"wheel_only":true,"yanked":false},"core_metadata":{"advertised_hash_and_actual_hash_must_match":true,"candidate_wheel_metadata_may_authorize_transitive_name_only_after_strict_parse":true,"exact_metadata_url_derived_from_verified_file_url":true,"external_sidecar_only_when_advertised":true,"raw_bytes_preserved":true,"when_sidecar_not_advertised":"V1C3A1 may fetch the exact selected wheel after declared/actual SHA-256 equality and extract only .dist-info/METADATA under bounded non-executing archive rules; the resulting candidate metadata must be independently reverified in V1C3A2"},"provenance":{"absence_recorded":true,"attestation_subject_filename_and_sha256_must_match_wheel":true,"captured_attempt_bytes_are_bound":true,"may_change_over_time":true,"object_version":1,"present_but_not_cryptographically_verified_blocks_acceptance":true,"present_url_must_be_secure_and_allowlisted":true,"proves_publishing_identity_not_package_safety":true,"raw_bytes_and_sha256_required":true},"resolver_output_authority":false,"simple_api":{"base_path":"/simple/","media_type":"application/vnd.pypi.simple.v1+json","minimum_minor":4,"non_active_project_status_blocks_selection":true,"normalized_optional_file_evidence_fields":["requires-python","yanked","core-metadata","upload-time","provenance"],"normalized_project_evidence_fields":["project-status.presence","project-status.status","project-status.reason"],"optional_field_absence_recorded_explicitly":true,"origin":"https://pypi.org","raw_required_project_fields":["meta","name","files","versions"],"raw_response_bytes_and_sha256_required":true,"selection_required_file_fields":["filename","url","hashes.sha256","size"],"supported_major":1,"unknown_fields":"preserve in raw bytes; ignore only when not selection-critical"}},"stage":"V1C3A1","strict_parsing":{"core_metadata":{"duplicate_or_conflicting_identity_fields":"reject","maximum_header_fields":8192,"maximum_line_bytes":65536,"maximum_marker_ast_nodes":1024,"maximum_marker_nesting_depth":64,"maximum_requirement_utf8_bytes":8192,"maximum_requires_dist_fields":4096,"name_version_requires_python_requires_dist_only_for_graph":true,"project_owned_supported_subset":true,"strict_header_and_line_bounds_required":true,"supported_metadata_versions":["2.1","2.2","2.3","2.4"],"unsupported_metadata_version_or_requirement_syntax":"fail closed"},"simple_json":{"duplicate_normalized_filenames_or_urls":"reject","duplicate_object_keys":"reject","encoding":"strict UTF-8 without BOM","integer_fields":"non-boolean, non-negative, signed-64-bit range","invalid_unicode_or_surrogates":"reject","maximum_array_items":16384,"maximum_nesting_depth":64,"maximum_object_members":16384,"maximum_string_utf8_bytes":4194304,"meta_api_version_required":true,"non_finite_numbers":"reject","project_name_must_normalize_to_requested_name":true,"root_type":"object","unknown_selection_critical_semantics":"fail closed"},"wheel_archive_candidate_metadata":{"allowed_compression_methods":["stored","deflate"],"candidate_parse_must_be_reverified_in_v1c3a2":true,"central_and_local_filename_must_match":true,"crc32_must_verify":true,"exact_archive_bounds":{"central_directory_bytes":8388608,"entries":16384,"member_extra_bytes":65536,"member_name_utf8_bytes":1024,"metadata_compression_ratio":100,"metadata_members":1,"metadata_uncompressed_bytes":4194304},"expanded_size_and_compression_ratio_bounds_required":true,"extract_only_dist_info_metadata":true,"no_package_import_or_execution":true,"only_when_external_core_metadata_sidecar_absent":true,"selected_wheel_declared_and_actual_sha256_match_first":true,"unsafe_path_duplicate_case_collision_encryption_symlink_or_unsupported_compression":"fail closed"}},"top_level_roadmap_expanded":false,"transition_target":{"network_authority_opened":false,"rc043":"ARCHITECTURE LOCK RECORDED","resolver_executed":false,"resolver_selected":false,"v1c3a1":"CURRENT / V1C3A1A NON-NETWORK CONTRACT ONLY / ACTIVE ACQUISITION BLOCKED"},"upstream_lineage":{"v1c0b2_external_source_authority":{"copied_authority_semantics_must_match":["PyPI Simple Repository API JSON v1 major 1 minimum minor 4","files.pythonhosted.org exact wheel URL from verified project response","resolver output proposal only","independent direct/transitive metadata and artifact verification","network only in dedicated bounded scrubbed host acquisition gates"],"current_committed_roadmap_exactly_one_identity_block_required":true,"decision_fingerprint":"80da155e8de0ce9f6d17565541173b701c2d5c9c8a8c13f1fcab9a57dbdb3d5e","decision_id":"skynetvs-v1c0b2-external-source-authority-lock-v1","incompatible_change_requires_separate_roadmap_decision":true,"rc043_entering_source_document":{"baseline_commit":"aa01155fb5b015faabc4aaf297c6cd7906334d9d","blob":"da8646b7ba2eb6e8b5dc5b3294640097fc86c37c","bytes":302136,"mode":"100644","path":"docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md","sha256":"bfc86dd318ef19e874041ec466a30fa1ccc8f7060d3afe3948d56334a3ad02fa","type":"blob"},"zero_multiple_or_mismatched_identity_blocks":"fail closed"},"v1c3a0_dependency_profile_target":{"copied_initial_scope_and_fixed_target_must_equal_current_policy":true,"current_imported_policy_id_and_fingerprint_must_match":true,"declaration_object_identity_must_match_profile_report":true,"dependency_profile_report_must_match_policy_id_and_fingerprint":true,"implementation_commit":"b7bd0b9ad449b0f10def37e27d9f93f272e996a1","implementation_tree":"cdf7591e242696a9976362801c6f200f26c71ded","incompatible_change_requires_separate_roadmap_decision":true,"missing_duplicate_or_mismatch":"fail closed","policy_fingerprint":"370e5d2c246be240b9d1a47fdebcc1250302155ea0e6128b6580079d5691748a","policy_id":"skynetvs-v1c3a0-dependency-profile-target-contract-v1","source":{"blob":"c383035a4363b0943aa25c53ac1ee3b0757e930b","bytes":19634,"mode":"100644","path":"modules/developer/developer_task_execution_dependency_profile_policy.py","sha256":"6cf4fa336a97ab9eba51aa9bee2f5912edaac1c35b696f89fc612fe95928b3c7","type":"blob"}},"v1c3a1a_required_issue_codes":["external_source_authority_lineage_changed","dependency_profile_policy_lineage_changed","dependency_profile_report_lineage_changed","dependency_profile_scope_or_target_copy_mismatch"]},"v1c3a1a_exact_mutable_scope":["modules/developer/developer_task_execution_dependency_acquisition.py","modules/developer/developer_task_execution_dependency_acquisition_policy.py","tools/eval_developer_task_execution_dependency_acquisition.py","tools/eval_developer_task_execution_dependency_acquisition_windows.py","tools/pipeline.py","tools/eval_package_boundaries.py"],"v1c3a1a_public_api":"build_developer_task_execution_dependency_acquisition_contract(dependency_profile_report, *, project_root) -> DeveloperTaskExecutionDependencyAcquisitionReport"}'


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({
            str(key): _freeze(item)
            for key, item in value.items()
        })
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _thaw(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _load_rc043_policy() -> dict[str, Any]:
    value = json.loads(_RC043_POLICY_CANONICAL_JSON)
    if not isinstance(value, dict):
        raise RuntimeError("RC043 canonical policy root must be an object")
    return value


_RC043_POLICY_PAYLOAD = _load_rc043_policy()
_POLICY_PAYLOAD: dict[str, Any] = {
    "schema_version": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_SCHEMA_VERSION,
    "policy_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_ID,
    "stage": "V1C3A1A",
    "architecture_policy": _RC043_POLICY_PAYLOAD,
}

DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_POLICY: Mapping[str, Any] = (
    _freeze(_RC043_POLICY_PAYLOAD)
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY: Mapping[str, Any] = (
    _freeze(_POLICY_PAYLOAD)
)


def canonical_developer_task_execution_dependency_acquisition_architecture_policy_json(
    policy: Mapping[str, Any] = (
        DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_POLICY
    ),
) -> str:
    if not isinstance(policy, Mapping):
        raise TypeError("policy must be a mapping")
    return (
        json.dumps(
            _thaw(policy),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )


def developer_task_execution_dependency_acquisition_architecture_policy_fingerprint(
    policy: Mapping[str, Any] = (
        DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_POLICY
    ),
) -> str:
    canonical = (
        canonical_developer_task_execution_dependency_acquisition_architecture_policy_json(
            policy
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_developer_task_execution_dependency_acquisition_policy_json(
    policy: Mapping[str, Any] = (
        DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY
    ),
) -> str:
    if not isinstance(policy, Mapping):
        raise TypeError("policy must be a mapping")
    return json.dumps(
        _thaw(policy),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def developer_task_execution_dependency_acquisition_policy_fingerprint(
    policy: Mapping[str, Any] = (
        DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY
    ),
) -> str:
    canonical = canonical_developer_task_execution_dependency_acquisition_policy_json(
        policy
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_developer_task_execution_dependency_acquisition_policy(
    policy: Mapping[str, Any] = (
        DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY
    ),
) -> tuple[str, ...]:
    if not isinstance(policy, Mapping):
        return ("policy_type_invalid",)

    errors: list[str] = []
    value = _thaw(policy)

    if value.get("schema_version") != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_SCHEMA_VERSION:
        errors.append("policy_schema_invalid")
    if value.get("policy_id") != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_ID:
        errors.append("policy_id_invalid")
    if value.get("stage") != "V1C3A1A":
        errors.append("policy_stage_invalid")

    architecture = value.get("architecture_policy")
    if not isinstance(architecture, dict):
        errors.append("policy_architecture_invalid")
        architecture = {}
    else:
        architecture_fingerprint = hashlib.sha256(
            (
                json.dumps(
                    architecture,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
        ).hexdigest()
        if (
            architecture_fingerprint
            != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT
        ):
            errors.append("policy_architecture_fingerprint_invalid")

    if architecture.get("decision_id") != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_ID:
        errors.append("policy_architecture_decision_invalid")
    if architecture.get("top_level_roadmap_expanded") is not False:
        errors.append("policy_top_level_roadmap_invalid")

    expected_scope = [
        "modules/developer/developer_task_execution_dependency_acquisition.py",
        "modules/developer/developer_task_execution_dependency_acquisition_policy.py",
        "tools/eval_developer_task_execution_dependency_acquisition.py",
        "tools/eval_developer_task_execution_dependency_acquisition_windows.py",
        "tools/pipeline.py",
        "tools/eval_package_boundaries.py",
    ]
    if architecture.get("v1c3a1a_exact_mutable_scope") != expected_scope:
        errors.append("policy_v1c3a1a_scope_invalid")
    if architecture.get("v1c3a1a_public_api") != (
        "build_developer_task_execution_dependency_acquisition_contract("
        "dependency_profile_report, *, project_root) -> "
        "DeveloperTaskExecutionDependencyAcquisitionReport"
    ):
        errors.append("policy_v1c3a1a_public_api_invalid")

    sequence = architecture.get("internal_sequence")
    if (
        not isinstance(sequence, list)
        or len(sequence) != 3
        or sequence[0] != {
            "artifact_bytes": False,
            "authority": False,
            "id": "V1C3A1A",
            "name": "non-network acquisition contract",
            "network": False,
            "resolver_execution": False,
        }
    ):
        errors.append("policy_internal_sequence_invalid")

    transition = architecture.get("transition_target")
    if transition != {
        "network_authority_opened": False,
        "rc043": "ARCHITECTURE LOCK RECORDED",
        "resolver_executed": False,
        "resolver_selected": False,
        "v1c3a1": (
            "CURRENT / V1C3A1A NON-NETWORK CONTRACT ONLY / "
            "ACTIVE ACQUISITION BLOCKED"
        ),
    }:
        errors.append("policy_transition_invalid")

    gates = architecture.get("gates")
    if not isinstance(gates, dict):
        errors.append("policy_gates_invalid")
    else:
        required_false = (
            "docs_lock_authorizes_network",
            "v1c3a1a_authorizes_network",
            "candidate_dependency_import_or_execution",
            "sandbox_launch",
            "reusable_lease",
            "execution_authorized",
            "resolver_tool_exact_version_selected_by_rc043",
            "resolver_tool_import_or_version_smoke_before_acceptance",
        )
        for key in required_false:
            if gates.get(key) is not False:
                errors.append(f"policy_gate_{key}_invalid")

        required_true = (
            "active_component_code_and_runtime_identity_must_be_bound_before_first_use",
            "archive_and_metadata_exact_bounds_must_be_enforced",
            "attempt_vs_closure_projection_contract_must_be_implemented_and_tested",
            "broker_os_egress_guard_must_be_proven_before_first_external_request",
            "copied_scope_and_target_must_equal_current_v1c3a0_policy",
            "graph_wide_no_extras_contract_must_be_enforced",
            "resolver_egress_guard_must_be_proven_before_first_use",
            "resolver_tool_manual_create_once_acceptance_required",
            "resolver_tool_record_license_and_security_acceptance_required_before_first_execution",
            "v1c0b2_external_source_authority_lineage_cross_check_required",
            "v1c3a0_dependency_profile_target_lineage_cross_check_required",
            "v1c3a2_offline_verification_required",
            "v1c3a3_manual_immutable_acceptance_required",
            "worker_process_filesystem_confinement_must_be_proven_before_first_use",
        )
        for key in required_true:
            if gates.get(key) is not True:
                errors.append(f"policy_gate_{key}_invalid")

    required_sections = {
        "active_component_identity",
        "active_worker_confinement",
        "bounds",
        "candidate_manifest",
        "environment",
        "evidence_layers",
        "extras_contract",
        "failure_and_storage",
        "fixed_target",
        "gates",
        "initial_scope",
        "internal_sequence",
        "marker_contract",
        "network_model",
        "resolver_capsule",
        "resolver_invocation",
        "resolver_output",
        "resolver_tool_acceptance",
        "resolver_tool_candidate",
        "source_authority",
        "strict_parsing",
        "transition_target",
        "upstream_lineage",
    }
    if not required_sections.issubset(set(architecture)):
        errors.append("policy_architecture_sections_incomplete")

    if (
        _CURRENT_DEPENDENCY_PROFILE_POLICY_ID
        != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_ID
    ):
        errors.append("policy_v1c3a0_policy_id_lineage_changed")
    if (
        _CURRENT_DEPENDENCY_PROFILE_POLICY_FINGERPRINT
        != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT
    ):
        errors.append("policy_v1c3a0_policy_fingerprint_lineage_changed")
    if (
        _current_dependency_profile_policy_fingerprint(
            _CURRENT_DEPENDENCY_PROFILE_POLICY
        )
        != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT
    ):
        errors.append("policy_v1c3a0_policy_semantics_lineage_changed")
    if _validate_current_dependency_profile_policy(
        _CURRENT_DEPENDENCY_PROFILE_POLICY
    ):
        errors.append("policy_v1c3a0_policy_self_check_failed")

    initial_scope = architecture.get("initial_scope")
    if not isinstance(initial_scope, dict) or initial_scope != {
        "blocked_profiles": [
            "skynetvs-nlu-training-minimal-v1",
            "skynetvs-python-base-whisper-v1",
        ],
        "declaration_paths": ["requirements.txt"],
        "profile_id": "skynetvs-python-base-v1",
        "requested_extras": [],
        "scope_expansion_requires_separate_roadmap_decision": True,
    }:
        errors.append("policy_initial_scope_invalid")

    current_profiles = tuple(
        item
        for item in _CURRENT_DEPENDENCY_PROFILE_POLICY.profiles
        if item.profile_id == "skynetvs-python-base-v1"
    )
    if len(current_profiles) != 1:
        errors.append("policy_v1c3a0_initial_profile_lineage_changed")
    else:
        current_profile = current_profiles[0]
        if (
            current_profile.declaration_paths != ("requirements.txt",)
            or current_profile.requested_extras
            or current_profile.initial_v1c3a_selected is not True
        ):
            errors.append("policy_v1c3a0_initial_profile_lineage_changed")

    expected_target = {
        "implementation_name": "cpython",
        "implementation_version": "3.13.15",
        "os_name": "nt",
        "platform_machine": "AMD64",
        "platform_python_implementation": "CPython",
        "platform_system": "Windows",
        "python_full_version": "3.13.15",
        "python_version": "3.13",
        "requested_extras": [],
        "sys_platform": "win32",
    }
    if architecture.get("fixed_target") != expected_target:
        errors.append("policy_target_invalid")
    if _CURRENT_DEPENDENCY_PROFILE_POLICY.target.to_dict() != expected_target:
        errors.append("policy_v1c3a0_target_lineage_changed")

    if (
        developer_task_execution_dependency_acquisition_policy_fingerprint(policy)
        != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_FINGERPRINT
    ):
        errors.append("policy_fingerprint_invalid")

    return tuple(errors)
