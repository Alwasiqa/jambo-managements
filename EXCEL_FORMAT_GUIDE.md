# 📊 Excel Import Format Guide

## 🎯 Quick Setup

**Excel mein columns ka order exactly yeh hona chahiye:**

| Col 1 | Col 2 | Col 3 | Col 4 | Col 5 | Col 6 | Col 7 | Col 8 | Col 9 | Col 10 | Col 11 | Col 12 | Col 13 | Col 14 |
|-------|-------|-------|-------|-------|-------|-------|-------|-------|--------|--------|--------|--------|--------|
| **Date** | **Jambo No** | **Size MM** | **Size Meter** | **Colour** | **Micron** | **Roll No** | **Net Weight** | **Party Name** | **Calc Yard** | **Actual Yard** | **Rate/KG** | **Amount** | **Extra Yard** |

## 📝 Detailed Column Description

### **Column 1: Date** 
- **Format:** YYYY-MM-DD
- **Examples:** 2025-01-15, 2024-12-20
- **Required:** Yes

### **Column 2: Jambo No**
- **Format:** Integer (Unique number)
- **Examples:** 2001, 2002, 2003
- **Required:** Yes
- **Note:** Must be unique, no duplicates

### **Column 3: Size MM**
- **Format:** Integer (Width in millimeters)
- **Examples:** 1280, 1000, 1600
- **Required:** Yes

### **Column 4: Size Meter**
- **Format:** Decimal (Length in meters)
- **Examples:** 4.5, 3.0, 5.2
- **Required:** Yes

### **Column 5: Colour**
- **Format:** Text (Upper case recommended)
- **Examples:** CLEAR, TAN, YELLOW, BLUE
- **Required:** Yes

### **Column 6: Micron**
- **Format:** Integer (Thickness)
- **Examples:** 100, 75, 50, 120
- **Required:** Yes

### **Column 7: Roll No**
- **Format:** Integer
- **Examples:** 1, 2, 3
- **Required:** Yes

### **Column 8: Net Weight**
- **Format:** Decimal (Weight in KG)
- **Examples:** 85.5, 62.0, 95.2
- **Required:** Yes

### **Column 9: Party Name**
- **Format:** Text
- **Examples:** Universal Coating, Ali Saddrudin, Capri Industries
- **Required:** Yes

### **Column 10: Calc Yard**
- **Format:** Integer (Calculated yards)
- **Examples:** 15000, 12000, 18000
- **Required:** Yes

### **Column 11: Actual Yard**
- **Format:** Integer (Actual yards available)
- **Examples:** 15000, 12000, 18000
- **Required:** Yes

### **Column 12: Rate/KG**
- **Format:** Decimal (Rate per kilogram)
- **Examples:** 185.50, 190.00, 175.00
- **Required:** Yes

### **Column 13: Amount**
- **Format:** Decimal (Total amount)
- **Examples:** 15860.25, 11780.00, 16660.00
- **Required:** Yes

### **Column 14: Extra Yard**
- **Format:** Integer (Extra yards, can be 0)
- **Examples:** 0, 100, 50
- **Required:** Yes (use 0 if no extra)

## 📋 Sample Data (Copy This Format)

```
2025-01-15	2001	1280	4.5	CLEAR	100	1	85.5	Universal Coating	15000	15000	185.50	15860.25	0
2025-01-15	2002	1000	3.0	TAN	75	2	62.0	Ali Saddrudin	12000	12000	190.00	11780.00	100
2025-01-16	2003	1600	5.0	YELLOW	120	1	95.2	Capri Industries	18000	18000	175.00	16660.00	50
```

## ⚠️ Important Notes

### ✅ DO:
- Excel mein headers NAHI dalna
- Data copy karte waqt sirf data rows select karna
- Jambo numbers unique rakhna
- Date format YYYY-MM-DD use karna

### ❌ DON'T:
- Challan No column NAHI dalna (system automatic handle karega)
- Headers include NAHI karna copy mein
- Empty rows NAHI dalna

## 🚀 Steps to Import

1. **Excel Setup:**
   - Create 14 columns in exact order
   - Fill data according to format
   - Select data rows (NO headers)

2. **Copy Data:**
   - Select all data rows
   - Press Ctrl+C

3. **Import:**
   - Go to `/jambos/excel-import` page
   - Paste data in textarea (Ctrl+V)
   - Click "Import Data"

4. **Review:**
   - Check import results
   - Fix any errors if needed
   - View imported jambos

## 🔒 Challan Protection

**System automatically:**
- Sets challan_no as empty
- Preserves challan sequence
- Allows manual challan assignment later
- Maintains data integrity

## 💡 Pro Tips

- Test with 2-3 rows first
- Check for duplicate jambo numbers
- Verify date formats
- Use "Show Sample" button for reference
- Import in batches for large datasets

**Ready to import your old stock! 🎬** 