# ParallelismPrediction
OpenSource Code for **Towards Parallelism Prediction of Sequential
Programs with Graph Neural Network**

This project is the implementation of our work on the parallelism prediction with graph neural network. 
Our framework leverages XFG-based data structure and DGCNN-based graph neural network model. About the original implementation
 of XFG and DGCNN, you can find the code here:  
 * **Neural Code Comprehension (XFG)**: (https://github.com/spcl/ncc)  
 * **DGCNN**: ( https://github.com/muhanzhang/DGCNN)  
 * **DGCNN-tensorflow**: (https://github.com/hitlic/DGCNN-tensorflow)
   
 
## Requirement  
Python3  
Tensorflow  
Pluto==0.11.4(http://pluto-compiler.sourceforge.net/)  
Clang/LLVM  
 
## Generating dataset  
We provide a dataset generator. This step assumes that you want generating your own dataset. You
 may add your source code manually to `data/source_code` , then run:  
`python3 data_gen.py` and `python3 test.py`  

**Note** that you need replace the `polycc` with your own.  

## Prediction  with neural network model  
Train and test:  
`python3 train.py`





 
 
