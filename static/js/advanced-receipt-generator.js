function advancedReceiptGenerator(hasSubscription = false) {
    return {
        // Settings
        currencyFormat: '$X',
        selectedFont: 'font-1',
        textColor: '#000000',
        showBackground: true,
        
        // Header
        logoUrl: '',
        headerAlignment: 'center',
        logoSize: 50,
        businessName: 'Business Details',
        headerDivider: '---',
        showHeaderDivider: true,
        
        // Date & Time
        dateAlignment: 'left',
        dateTime: '',
        dateDivider: '---',
        showDateDivider: true,
        
        // Two Column Info
        customFields: [
            { label: 'Table', value: '415' },
            { label: 'Server', value: 'Rebecca' },
            { label: 'Guests', value: '2', column: 2 }
        ],
        infoDivider: '---',
        showInfoDivider: true,
        
        // Items
        items: [
            { quantity: 1, name: 'Americano', price: 2.99 },
            { quantity: 2, name: 'Chocolate Chip Cookie', price: 1.98 },
            { quantity: 2, name: 'Coke', price: 1.5 }
        ],
        itemsDivider: '---',
        showItemsDivider: true,
        
        // Payment
        paymentType: 'cash',
        paymentFields: [
            { label: 'Cash', value: '6' },
            { label: 'Change', value: '0.53' }
        ],
        paymentDivider: '---',
        showPaymentDivider: true,
        
        // Totals
        taxRate: 4,
        
        // Custom Message
        customMessage: 'THANK YOU\nHAVE A NICE DAY',
        messageAlignment: 'center',
        messageDivider: '---',
        showMessageDivider: false,
        
        // Barcode
        barcodeEnabled: true,
        barcodeSize: 50,
        barcodeLength: 50,
        barcodeDivider: '---',
        showBarcodeDivider: false,
        
        // Watermark controlled server-side only
        
        // Computed
        get subtotal() {
            return this.items.reduce((sum, item) => sum + (parseFloat(item.price) || 0) * (parseInt(item.quantity) || 0), 0);
        },
        
        get tax() {
            return this.subtotal * (this.taxRate / 100);
        },
        
        get total() {
            return this.subtotal + this.tax;
        },
        
        get column1Fields() {
            return this.customFields.filter(f => !f.column || f.column === 1);
        },
        
        get column2Fields() {
            return this.customFields.filter(f => f.column === 2);
        },
        
        removeColumnField(field) {
            const index = this.customFields.indexOf(field);
            if (index > -1) {
                this.customFields.splice(index, 1);
            }
        },
        
        // Methods
        formatCurrency(amount) {
            const formatted = amount.toFixed(2);
            switch(this.currencyFormat) {
                case '$X': return '$' + formatted;
                case 'X$': return formatted + '$';
                case 'X $': return formatted + ' $';
                default: return '$' + formatted;
            }
        },
        
        addItem() {
            this.items.push({ quantity: 1, name: '', price: 0 });
        },
        
        removeItem(index) {
            this.items.splice(index, 1);
        },
        
        addCustomField(column = 1) {
            this.customFields.push({ label: '', value: '', column });
        },
        
        removeCustomField(index) {
            this.customFields.splice(index, 1);
        },
        
        addPaymentField() {
            this.paymentFields.push({ label: '', value: '' });
        },
        
        removePaymentField(index) {
            this.paymentFields.splice(index, 1);
        },
        
        uploadLogo(event) {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    this.logoUrl = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        },
        
        getDivider(style) {
            const dividers = {
                '---': '----------------------------------------',
                '===': '========================================',
                '...': '........................................',
                ':::': '::::::::::::::::::::::::::::::::::::::::',
                '***': '****************************************'
            };
            return dividers[style] || dividers['---'];
        },
        
        generateBarcode() {
            const length = Math.floor(this.barcodeLength / 10);
            let code = '';
            for (let i = 0; i < length; i++) {
                code += Math.floor(Math.random() * 10);
            }
            return code;
        },
        
        downloadReceipt() {
            window.print();
        },
        
        resetForm() {
            location.reload();
        },
        
        // Watermark removal only for paid users - controlled server-side
        
        init() {
            this.dateTime = new Date().toLocaleString();
        }
    }
}
