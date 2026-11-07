"""Private Studio replay projection of a reviewed run's observations."""
import uuid


def reviewed_replay(report):
    container = report['container']
    broker = report['broker']
    provider = broker['provider']
    events = [{
        'id': 'root', 'parent_id': None, 'type': 'execution',
        'label': 'Contained specification run', 'status': report['status'],
        'details': {'container_status': container['status'],
                    'policy_verified': container.get('policy_verified'),
                    'cleanup_verified': container.get('cleanup_verified')},
    }]
    completions = 0
    for index, event in enumerate(broker['events'], 1):
        if event['status'] == 'completed':
            completions += 1
        events.append({
            'id': f'broker-{index}', 'parent_id': 'root', 'type': 'broker',
            'label': f'Host broker request {index}', 'status': event['status'],
            'details': {key: event[key] for key in ('id', 'prompt_sha256', 'response_sha256',
                                                   'error_classification') if key in event},
        })
    if report['context_reported'] is not None or report['subcall_reported'] is not None:
        events.append({
            'id': 'runtime-observations', 'parent_id': 'root', 'type': 'runtime',
            'label': 'Container-reported observations', 'status': 'reported',
            'details': {'context_inspection': report['context_reported'],
                        'completed_subcall': report['subcall_reported']},
        })
    return {
        'schema_version': 1, 'id': 'private-' + uuid.uuid4().hex, 'label': 'Reviewed specification replay',
        'mode': 'private-reviewed-replay', 'visibility': 'private', 'status': report['status'],
        'live_inference': None, 'events': events, 'artifacts': [],
        'metrics': {'broker_completions': completions, 'reserved_calls': provider['reserved_calls'],
                    'output_tokens_reserved': provider['output_tokens_reserved'],
                    'estimated_cost_committed_usd': provider['estimated_cost_committed_usd'],
                    'validated_source_files': report['artifact_count'],
                    'functional_success': None, 'cost_usd': None},
    }
