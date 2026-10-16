# Manual de uso – IA Off 3.0 (esqueleto; detalhes após o polimento da interface)

1. Abrir o app (atalho "IA Off" na Área de Trabalho)
2. Chat: escolher modelo, conversar, histórico, importar GGUF
3. Documentos: importar PDF/Word/TXT, perguntar, ver a fonte citada
4. Imagem: texto para imagem, transformar, pintar por cima, editar por instrução; proporção e resolução
   - Recomendado: OpenVINO na GPU Intel. Imagem 512, 4 passos, no PC do Julio: GPU 17,5 s; OpenVINO CPU 29 s; PyTorch CPU 36 s.
   - Ampliar 2x ou 4x: cerca de 4 s.
5. Vídeo (Wan 2.1): gerar, acompanhar o progresso, cancelar
   - Tempo esperado: um vídeo curto de 480x272 leva cerca de 1h30 (uns 9 min carregando, 65 min gerando a ~200 s por passo, 16 min decodificando). CPU e GPU dão o mesmo tempo; o padrão é CPU, que deixa a GPU livre.
6. Fila de tarefas: o que significa cada estado
7. Voz: transcrição (Whisper) e fala (Piper)
8. Modo turbo e Benchmark
9. Onde ficam os modelos e dados (`C:\IA\modelos`, `C:\IA\dados`) e como adicionar um modelo novo
10. Problemas comuns e soluções
