from helpers import load_data
import analysis
import prediction

def main():
    print("========================================")
    print("   KIRANA-PREDICT: INVENTORY SYSTEM    ")
    print("========================================\n")
    
    # 1. Ask the user what they want to do
    print("1. View Top Selling Items & Weekly Trends")
    print("2. Generate Next Week's Restock Report")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ")

    if choice == '1':
        # Your analysis logic already prints when imported, 
        # but in a real app, we'd wrap it in a function.
        print("\nDisplaying Sales Analysis...")
        # Since analysis.py runs on import, it will show up here.
        
    elif choice == '2':
        print("\nGenerating Restock Report...")
        # Your prediction logic already prints when imported.
        
    elif choice == '3':
        print("Exiting... Happy selling!")
    else:
        print("Invalid choice. Please run again.")

if __name__ == "__main__":
    main()