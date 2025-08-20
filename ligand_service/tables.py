import django_tables2 as tables


class ContactsTable(tables.Table):
    frame = tables.Column()
    interaction_type = tables.Column()
    atom_1 = tables.Column()
    atom_2 = tables.Column()
    atom_3 = tables.Column()
    atom_4 = tables.Column()


class ContactsTableNumbered(tables.Table):
    frame = tables.Column()
    interaction_type = tables.Column()
    numbered_residue = tables.Column()
    atom_1 = tables.Column()
    atom_2 = tables.Column()
    atom_3 = tables.Column()
    atom_4 = tables.Column()
