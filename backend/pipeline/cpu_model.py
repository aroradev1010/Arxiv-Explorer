"""Optional full-precision OpenVINO encoder; ST still handles tokenization/pooling."""
from pathlib import Path
import torch
from sentence_transformers import SentenceTransformer
from .common import read_json, sha256, write_json


def load_model(model_path: str, threads: int = 4, optimized: bool = False):
    torch.set_num_threads(threads)
    model = SentenceTransformer(model_path, device='cpu', local_files_only=True)
    if not optimized:
        return model
    import openvino as ov
    cache = Path(model_path).parent / (Path(model_path).name + '-openvino-f32')
    cache.mkdir(parents=True, exist_ok=True)
    fingerprint = sha256(Path(model_path) / 'model.safetensors')
    config_fingerprint = sha256(Path(model_path) / 'config.json')
    xml = cache / 'encoder.xml'
    if xml.exists():
        source = read_json(cache / 'source.json')
        if source['weights_sha256'] != fingerprint or source.get('config_sha256') != config_fingerprint:
            raise ValueError('Optimized encoder does not match source weights')
        graph = ov.Core().read_model(str(xml))
    else:
        class Encoder(torch.nn.Module):
            def __init__(self, original):
                super().__init__()
                self.original = original

            def forward(self, input_ids, attention_mask, token_type_ids):
                return self.original(input_ids=input_ids, attention_mask=attention_mask,
                                     token_type_ids=token_type_ids, return_dict=True).last_hidden_state

        encoder = Encoder(model[0].model).eval()
        example = model.preprocess(['Scientific research in quantum field theory.'])
        graph = ov.convert_model(encoder,
                                 example_input=(example['input_ids'], example['attention_mask'], example['token_type_ids']),
                                 input=[([-1, -1], ov.Type.i64)] * 3)
        ov.save_model(graph, str(xml), compress_to_fp16=False)
        write_json(cache / 'source.json', {'weights_sha256': fingerprint,
                                         'config_sha256': config_fingerprint,
                                         'precision': 'float32', 'quantized': False})
    compiled = ov.Core().compile_model(graph, 'CPU', {'INFERENCE_PRECISION_HINT': 'f32',
                                                      'INFERENCE_NUM_THREADS': threads,
                                                      'NUM_STREAMS': 1})

    class Adapter(torch.nn.Module):
        def __init__(self, config):
            super().__init__()
            self.config = config
            self.device = torch.device('cpu')
            self.dtype = torch.float32

        def forward(self, input_ids, attention_mask, token_type_ids=None, **kwargs):
            if token_type_ids is None:
                token_type_ids = torch.zeros_like(input_ids)
            result = compiled([input_ids.numpy(), attention_mask.numpy(), token_type_ids.numpy()])
            # Clone because the inference request's output buffer is reused on the next call.
            return {'last_hidden_state': torch.from_numpy(result[compiled.output(0)].copy())}

    model[0].model = Adapter(model[0].model.config)
    return model
