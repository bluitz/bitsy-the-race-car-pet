ssh jmunning@10.0.0.82 'echo "Hi, I am Bitsy Munning, and I love racing cars!" | espeak-ng -v mb-us1 -p 200 -s 175 -g 10'
ssh jmunning@10.0.0.82 "espeak-ng -v mb-us2 'Testing the voice output'"
ssh -t jmunning@10.0.0.82 "cd ~ && source venv/bin/activate && python3 chatgpt.py"
sh jmunning@10.0.0.82 'echo "Hi! I am Bitsy Munning and I love racing cars!" | /home/jmunning/piper/piper --model ~/.local/share/piper/en_US-amy-medium.onnx --output_file /tmp/test.wav && aplay /tmp/test.wav'
ssh -t jmunning@10.0.0.82 "cd ~ && source venv/bin/activate && python3 chatgpt_with_leds_final.py"