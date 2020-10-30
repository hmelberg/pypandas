import itertools
from .series import Series
from .indexers import ILocDF, LocDF
from .other_stuff import nan, is_bool, is_2d_bool


class DataFrame:
    """
    The only mutable attribute is the data.
    Shape is equal to the view.
    If a row is added, data is recreated and step is also updated.
    If a column is added, data is appended *only* if the dataframe view covers
    the entire dataset (shape equals len index, columns). Otherwise, a copy is made
    View is a tuple of two slices, for the row and column. Steps are not taken into
    account in view, it is high level. This is contrary to Series
    step = len(index) = shape(0) = view[0].stop - view[0].start
    len(columns) = shape(1) = view[1].stop - view[1].start
    """

    ITERABLE_1D = (list, set, tuple, Series)

    def __init__(self, data=None, index=None, columns=None):
        self.columns = tuple(columns) if columns else tuple()  # type: tuple
        self.index = tuple(index) if index else tuple()  # type: tuple
        self.data = []  # type: list
        self.step = 0  # type: int
        self.shape = (0, 0)  # type: tuple
        self.view = (slice(0, 0), slice(0, 0))  # type: tuple
        self.iloc = ILocDF(self)  # type: ILocDF
        self.loc = LocDF(self)  # type: LocDF

        if data is None:
            return
        if isinstance(data, dict):
            self.step = len(data[list(data.keys())[0]])
            self.data = list(itertools.chain(*data.values()))
            self.columns = tuple(data.keys())
        elif isinstance(data, list):
            if isinstance(data[0], self.ITERABLE_1D):
                self.step = len(data)
                data = list(zip(*data))
                for item in data:
                    self.data.extend(item)
            elif isinstance(data[0], dict):
                for d_dict in data:
                    key, val = next(iter(d_dict.items()))
                    self.columns = self.columns + (key,)
                    self.data.extend(val)
                self.step = len(val)

        if len(self.columns) == 0:
            self.columns = tuple(i for i in range(len(self.data) // self.step))

        if len(self.index) == 0:
            self.index = tuple(i for i in range(self.step))
        self.shape = (self.step, len(self.columns))
        self.view = (slice(0, self.shape[0]), slice(0, self.shape[1]))

    @classmethod
    def from_data(cls, data, index, columns, view, step):
        self = cls()
        self.data = data
        self.columns = columns
        self.index = index
        self.view = view
        self.step = step
        self.shape = (
            self.view[0].stop - self.view[0].start,
            self.view[1].stop - self.view[1].start,
        )
        self.iloc = ILocDF(self)
        self.loc = LocDF(self)

        return self

    @classmethod
    def class_init(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    @classmethod
    def series_from_data(cls, *args):
        return Series.from_data(*args)

    def __str__(self):
        string = "DataFrame: " + "\n" + str(self.columns) + "\n"
        string += "\n".join(str(d) for d in zip(self.index, self.values))
        return string

    def __getitem__(self, cols):
        # gets here as slice and series
        if isinstance(cols, tuple):
            return self.loc[cols]
        elif isinstance(cols, slice) or is_bool(cols) or is_2d_bool(cols):
            print("Found a 2d array. Passing as item[0]")
            return self.loc[cols, :]
        else:
            return self.loc[:, cols]

    def __setitem__(self, key, value):
        """
        This implementation just adds a new columns
        :param key:
        :param value:
        :return:
        """
        # if it is a single item, call .loc[:, key]
        # if is a slice, call .loc[key, :]
        # if its an iterable call .loc[:, key]
        if isinstance(key, (tuple, self.__class__)):
            self.loc[key] = value
        elif isinstance(key, slice) or is_bool(key):
            self.loc[key, :] = value
        else:
            self.loc[:, key] = value

    def __delitem__(self, cols):
        self.drop(cols)

    def __lt__(self, other):
        df = self.copy()
        df.data = [item < other for item in df.data]
        return df

    def __le__(self, other):
        df = self.copy()
        df.data = [item <= other for item in df.data]
        return df

    def __gt__(self, other):
        df = self.copy()
        df.data = [item > other for item in df.data]
        return df

    def __ge__(self, other):
        df = self.copy()
        df.data = [item >= other for item in df.data]
        return df

    def __eq__(self, other):
        df = self.copy()
        df.data = [item == other for item in df.data]
        return df

    def __ne__(self, other):
        df = self.copy()
        df.data = [item != other for item in df.data]
        return df

    def __iter__(self):
        return iter(self.columns)

    def __invert__(self):
        df_cp = self.copy()
        for i, val in enumerate(df_cp.data):
            df_cp.data[i] = not df_cp.data[i]
        return df_cp

    def __len__(self):
        return self.shape[0]

    def drop(self, labels=None):
        """
        Drop both removes a specified column and trims internal data, producing a copy.

        column_index: a column to drop
        :return:
        """
        to_delete = self.view[1].stop
        num = 0
        if isinstance(labels, str):
            to_delete = self.columns.index(labels)
            num = 1

        # build new dataset without the old columns
        data_cols = []

        for col_index in range(self.view[1].start, to_delete):
            data_cols.append(
                self.data[
                    self.view[0].start
                    + col_index * self.step : self.view[0].stop
                    + col_index * self.step
                ]
            )

        for col_index in range(to_delete + num, self.view[1].stop):
            data_cols.append(
                self.data[
                    self.view[0].start
                    + col_index * self.step : self.view[0].stop
                    + col_index * self.step
                ]
            )
        self.data = []
        for col in data_cols:
            self.data.extend(col)

        #    and adjust our indexing
        self.columns = self.columns[0:to_delete] + self.columns[to_delete + num :]
        self.shape = (self.shape[0], self.shape[1] - num)
        self.view = (slice(0, len(self.index)), slice(0, len(self.columns)))
        self.step = len(self.index)

    def copy(self):
        """
        Creates a copy of the dataframe and trims the data with self.drop
        :return:
        """
        df = DataFrame.from_data(
            self.data, self.index, self.columns, self.view, self.step
        )
        df.drop()
        return df

    def equals(self, other):

        return (self.values == other.values) and (self.shape == other.shape)

    @property
    def values(self):
        data_rows = []
        for row_index in range(self.view[0].start, self.view[0].stop):
            data_rows.append(
                self.data[
                    row_index
                    + self.step * self.view[1].start : row_index
                    + self.step * self.view[1].stop : self.step
                ]
            )
        return data_rows

    def bound_int_to_df(self, raw_int, axis):
        """
        Transforms an index int to the actual axis index of data, taking bounds into account
        e.g.
        [0,| 1, 2, 3, 4, 5, | 6]
        If `2` is given, it should access "3", thus index 2 is actually 3.
        -1 becomes 5
        6 would be an index error
        Slices are handled by a bound_slice_to_df

        :param raw_int:
        :param axis:
        :return:
        """
        if axis in [0, "row", "rows"]:
            view_min = self.view[0].start
            view_max = self.view[0].stop
        elif axis in [1, "column", "columns"]:
            view_min = self.view[1].start
            view_max = self.view[1].stop
        else:
            raise UserWarning

        # handle negative ints
        if raw_int < 0:
            start = view_max + raw_int
        else:
            start = view_min + raw_int

        # check bounds
        if start > view_max or start < view_min:
            raise IndexError

        return start

    def bound_slice_to_df(self, raw_slice, axis):
        """
        Transforms a slice to the actual axis view for the data
        :param raw_slice: relative slice
        :return: slice to underlying data
        """
        if axis in [0, "row", "rows"]:
            view_start = self.view[0].start
            view_stop = self.view[0].stop
        elif axis in [1, "column", "columns"]:
            view_start = self.view[1].start
            view_stop = self.view[1].stop
        else:
            pass

        if raw_slice.start:
            if raw_slice.start < 0:
                start = max(view_stop + raw_slice.start, view_start)
            else:
                start = min(view_start + raw_slice.start, view_stop)
        else:
            start = view_start

        if raw_slice.stop:
            if raw_slice.stop < 0:
                stop = max(view_stop + raw_slice.stop, view_start)
            else:
                stop = min(view_start + raw_slice.stop, view_stop)
        else:
            stop = view_stop
        return slice(start, stop)

    def bound_iterable_to_df(self, raw_iter, axis):
        """
        Converts indicies to the actual data indicies
        :param raw_iter:
        :param axis:
        :return:
        """
        return [self.bound_int_to_df(item, axis) for item in raw_iter]

    def convert_slice(self, raw_slice, axis):
        """
        Removes the None from the slice and replaces it with length of rows or columns.
        doesn't adjust based on view
        :param raw_slice:
        :param axis:
        :return:
        """
        if axis in [0, "row", "rows"]:
            max_stop = len(self.index)
        elif axis in [1, "columns", "cols", "col"]:
            max_stop = len(self.columns)

        if not raw_slice.start:
            start = 0
        elif raw_slice.start < 0:
            start = max(0, max_stop + raw_slice.start)
        else:
            start = raw_slice.start

        if not raw_slice.stop:
            stop = max_stop
        elif raw_slice.stop < 0:
            stop = max(0, max_stop + raw_slice.stop)
        else:
            stop = raw_slice.stop
        return slice(start, stop)

    def is_view(self):
        """
        Determines whether or not the dataframe is a view of another dataframe.
        Checks if the shape is the sshape of the entire data
        :return:
        """
        return self.shape[0] != self.step or self.shape[1] != len(self.data) / self.step

    def index_of(self, item, axis=0):
        """
        Returns the integer index of a column/index label
        :param item: iterable or label
        :param axis: 0 - search index; 1 - search column labels
        :return: list(int) or int
        """
        if axis in [0, "rows", "row"]:
            names = self.index
        else:
            names = self.columns
        if isinstance(item, self.ITERABLE_1D):
            # bypass for boolean
            if is_bool(item):
                return item
            return [names.index(i) for i in item]
        elif isinstance(item, slice):
            start = None if item.start is None else names.index(item.start)
            stop = None if item.stop is None else names.index(item.stop)
            return slice(start, stop)
        else:
            try:
                return names.index(item)
            except:
                return None

    def add_empty_series(self, name, axis=0):
        """
        Adds a new row/column to a dataframe.

        If the dataframe is a view, it will make a copy of itself and trim its
        :param name: Index/column name
        :param axis: int; 0 - adds a row. 1 - adds a column
        :return: None. Does so in place.
        """
        # if its a view, make a copy
        if self.is_view():
            self.drop()

        # Add a row
        if axis == 0:
            self.index = self.index + (name,)
            ndata = []
            for i in range(self.shape[1]):
                ndata.extend(self.data[i * self.step : (i + 1) * self.step] + [nan])
            self.data = ndata
            self.shape = (self.shape[0] + 1, self.shape[1])
            self.view = (slice(self.view[0].start, self.view[0].stop + 1), self.view[1])
            self.step = self.step + 1
        # add a column
        elif axis == 1:
            self.columns = self.columns + (name,)
            self.data = self.data + [nan] * self.shape[0]
            self.shape = (self.shape[0], self.shape[1] + 1)
            self.view = (self.view[0], slice(self.view[1].start, self.view[1].stop + 1))

    def append(self, other, ignore_index=True):

        columns = self.columns + tuple(
            col for col in other.columns if col not in self.columns
        )
        data_columns = []
        for col in columns:
            if col in self.columns:
                temp = self[col].values
            else:
                temp = [nan] * len(self)
            if col in other.columns:
                temp += other[col].values
            else:
                temp += [nan] * len(other)
            data_columns.append(temp)
        if ignore_index:
            index = None
        else:
            index = self.index + other.index
        return self.class_init(
            {k: v for k, v in zip(columns, data_columns)}, index=index
        )
