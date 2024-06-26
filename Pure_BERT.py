import json
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer, BertModel
import torch.nn as nn
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler
import numpy as np
import logging
from utils import read_multiple_jsonl_files, convert_labels_to_indices, train_BERT


# Configure logging
logging.basicConfig(filename='/root/yyx/Multiple_Detection/logs/train_BERT.log', level=logging.INFO, format='%(asctime)s %(message)s')

MAX_LENGTH = 512
PARTITIAL = 1
LR = 1e-5
BATCH_SIZE = 32
NUM_EPOCHS = 8
LOG_ITER = 50

# Define label to index mapping
label_to_index = {'llama': 0, 'human': 1, 'gptneo': 2, 'gpt3re': 3, 'gpt2': 4}
num_classes = len(label_to_index)

# Define custom dataset class
class TextDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]

        encoding = self.tokenizer(text, truncation=True, padding='max_length', max_length=self.max_length,
                                  return_tensors='pt')

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'label': torch.tensor(label, dtype=torch.long)
        }

# Define model class
class AIGTClassifier(nn.Module):
    def __init__(self, pretrained_model_name, num_classes):
        super(AIGTClassifier, self).__init__()
        self.bert = BertModel.from_pretrained(pretrained_model_name)
        self.fc1 = nn.Linear(self.bert.config.hidden_size, 128)  
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output
        
        # # Standardize the BERT features
        # standardizer = StandardScaler()
        # pooled_output = standardizer.fit_transform(pooled_output.cpu().detach().numpy())

        intermediate_output = self.fc1(pooled_output)
        intermediate_output = torch.relu(intermediate_output)
        logits = self.fc2(intermediate_output)
        return logits

# Load BERT tokenizer
tokenizer = BertTokenizer.from_pretrained('/root/yyx/Multiple_Detection/bert-base-cased')

# Define maximum length
max_length = MAX_LENGTH

# Read data from JSONL files
file_paths = [
    '/root/yyx/Multiple_Detection/dataset/en_gpt2_lines.jsonl',
    '/root/yyx/Multiple_Detection/dataset/en_gpt3_lines.jsonl',
    '/root/yyx/Multiple_Detection/dataset/en_gptneo_lines.jsonl',
    '/root/yyx/Multiple_Detection/dataset/en_human_lines.jsonl',
    '/root/yyx/Multiple_Detection/dataset/en_llama_lines.jsonl'
]  
texts, labels = read_multiple_jsonl_files(file_paths)
# Convert labels to indices
labels = convert_labels_to_indices(labels, label_to_index)



# Create dataset
dataset = TextDataset(texts, labels, tokenizer, max_length)
# Split dataset into train and test sets 
train_size = int(0.8 * len(dataset))
test_size = len(dataset) - train_size
train_dataset, test_dataset = torch.utils.data.random_split(dataset, [train_size, test_size])
# Use a smaller portion of the dataset to speed up training and testing
subset_train_size = int(PARTITIAL * train_size)
subset_test_size = int(PARTITIAL * test_size)
train_dataset, _ = torch.utils.data.random_split(train_dataset, [subset_train_size, train_size - subset_train_size])
test_dataset, _ = torch.utils.data.random_split(test_dataset, [subset_test_size, test_size - subset_test_size])
# Create DataLoaders
train_dataloader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
test_dataloader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=True)

# Define model
pretrained_model_name = '/root/yyx/Multiple_Detection/bert-base-cased'
model = AIGTClassifier(pretrained_model_name, num_classes)

# Define loss function and optimizer
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
# scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.1)
scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lambda epoch: 1.0)


# Move model to GPU if available
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)
logging.info("="*50)
print("="*50)
logging.info(f"Training Pure BERT with LR-{LR}...")
print(f"Training Pure BERT with LR-{LR}...")
# Train the model
train_BERT(model, train_dataloader, test_dataloader, criterion, optimizer, scheduler, NUM_EPOCHS, LOG_ITER, device)
logging.info(f"Training finished!")
print(f"Training finished!")
logging.info("="*50)
print("="*50)