#include "stdio.h"
int fun(int fibo[100],int temp){
int i=0,n=10;
for(i = 2;i<n;i++){
temp=fibo[i-1]+fibo[i-2];
fibo[i]=temp;
}
}
