@echo off
echo COMANDO: "G:\Outros computadores\USB e dispositivos externos\Pen IA\llamafile-0.10.3.exe.exe" -m "G:\Outros computadores\USB e dispositivos externos\Pen IA\qwen2.5-coder-7b-instruct-q3_k_m.gguf" --server --port 8082 --gpu disable -c 16384 -t 6 -tb 12 -b 2048 -ub 512 --parallel 1 --no-warmup --cache-ram 6144 --no-mmap > "G:\Meu Drive\projetos\Cerebro\motor.log"
echo. >> "G:\Meu Drive\projetos\Cerebro\motor.log"
"G:\Outros computadores\USB e dispositivos externos\Pen IA\llamafile-0.10.3.exe.exe" -m "G:\Outros computadores\USB e dispositivos externos\Pen IA\qwen2.5-coder-7b-instruct-q3_k_m.gguf" --server --port 8082 --gpu disable -c 16384 -t 6 -tb 12 -b 2048 -ub 512 --parallel 1 --no-warmup --cache-ram 6144 --no-mmap >> "G:\Meu Drive\projetos\Cerebro\motor.log" 2>&1
