function receiptGenerator() {
    return {
        selectedTemplate: '',
        businessName: '',
        address: '',
        phone: '',
        date: new Date().toISOString().split('T')[0],
        time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
        items: [
            { name: 'Sample Item', quantity: 1, price: 10.00 }
        ],
        taxRate: 8.5,
        paymentMethod: 'Cash',
        cardLast4: '',
        receiptNumber: '',
        customMessage: 'Thank you for your purchase!',
        
        get subtotal() {
            return this.items.reduce((sum, item) => {
                return sum + ((parseFloat(item.price) || 0) * (parseInt(item.quantity) || 1));
            }, 0);
        },
        
        get tax() {
            return this.subtotal * (parseFloat(this.taxRate) || 0) / 100;
        },
        
        get total() {
            return this.subtotal + this.tax;
        },
        
        addItem() {
            this.items.push({ name: '', quantity: 1, price: 0 });
        },
        
        removeItem(index) {
            this.items.splice(index, 1);
        },
        
        downloadReceipt() {
            window.print();
        },
        
        init() {
            // Initialize with template data if available
            const urlParams = new URLSearchParams(window.location.search);
            const templateSlug = window.location.pathname.split('/').pop();
            
            // Set template name as business name if coming from a template page
            if (this.selectedTemplate && this.businessName === '') {
                // Business name already set from server
            }
        }
    }
}
